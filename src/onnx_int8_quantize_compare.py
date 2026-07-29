"""
ONNX cross-encoder 리랭커를 int8 동적 양자화로 줄이는 PoC.

실제 운영 리랭커(~1.1GB)를 그대로 쓸 수 없으므로, 같은 형태(행렬곱 여러 층)의
축소판 ONNX 모델을 직접 만들어 fp32 대 int8의 "파일 크기"와 "추론 시간"을
비교한다. onnxruntime.quantization.quantize_dynamic이 이 환경에서 동작하면
실제로 양자화를 적용하고, 실패하면(예: onnx/onnxruntime 버전 불일치) 목(mock)
경로로 실측 비율만 축소 모델에 대입해 추정치를 보여준다.

정확도는 이 축소 모델로는 의미 있게 측정할 수 없다. 실제 운영 리랭커에서
직접 측정한 값(REAL_WORLD_BENCHMARK)을 그대로 인용해 트레이드오프 표에 함께
보여준다. "성능이 좋아졌다"는 말이 정확도인지 속도인지를 헷갈리지 않도록,
두 지표를 절대 한 줄에 섞지 않는다.
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stdout)
logger = logging.getLogger("OnnxInt8QuantizeCompare")

MODEL_DIR = Path(__file__).parent / "downloads" / "onnx_quant_demo"
FP32_PATH = MODEL_DIR / "reranker_toy_fp32.onnx"
INT8_PATH = MODEL_DIR / "reranker_toy_int8.onnx"

HIDDEN = 384  # 실제 cross-encoder의 hidden dim 규모를 흉내낸 크기
LAYERS = 6
N_RUNS = 30

# 실제 운영 리랭커에서 직접 측정한 값. 이 스크립트가 만드는 축소 모델로는
# 재현할 수 없으므로 실측 인용값으로만 사용한다. 지어낸 값이 아니다.
REAL_WORLD_BENCHMARK = {
    "fp32": {"accuracy": 0.839, "latency_ms": 1034, "size_gb": 1.11},
    "int8": {"accuracy": 0.774, "latency_ms": 760, "size_gb": 0.28},  # 741~781ms 실측 구간의 중간값
}


def build_toy_reranker(path: Path, hidden: int = HIDDEN, layers: int = LAYERS) -> None:
    """cross-encoder를 흉내낸 축소 ONNX 모델(행렬곱 + ReLU 반복)을 만들어 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    inputs = [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, hidden])]
    outputs = [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, hidden])]

    nodes = []
    initializers = []
    prev = "input"
    for i in range(layers):
        w_name = f"w{i}"
        b_name = f"b{i}"
        out_name = f"h{i}" if i < layers - 1 else "output"

        weight = rng.standard_normal((hidden, hidden), dtype=np.float32) * 0.02
        bias = rng.standard_normal((hidden,), dtype=np.float32) * 0.02
        initializers.append(helper.make_tensor(w_name, TensorProto.FLOAT, weight.shape, weight.flatten()))
        initializers.append(helper.make_tensor(b_name, TensorProto.FLOAT, bias.shape, bias.flatten()))

        gemm_out = out_name if i == layers - 1 else f"{out_name}_pre"
        nodes.append(helper.make_node("Gemm", [prev, w_name, b_name], [gemm_out], name=f"gemm{i}"))
        if i < layers - 1:
            nodes.append(helper.make_node("Relu", [gemm_out], [out_name], name=f"relu{i}"))
        prev = out_name

    graph = helper.make_graph(nodes, "toy_cross_encoder", inputs, outputs, initializers)
    model = helper.make_model(graph, producer_name="onnx_int8_quantize_compare")
    model.opset_import[0].version = 13
    onnx.checker.check_model(model)
    onnx.save(model, str(path))
    logger.info("fp32 축소 모델 생성: %s (%d층, hidden=%d)", path, layers, hidden)


def try_quantize_dynamic(fp32_path: Path, int8_path: Path) -> bool:
    """가능하면 진짜 quantize_dynamic으로 양자화한다. 실패하면 False를 반환한다."""
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        quantize_dynamic(str(fp32_path), str(int8_path), weight_type=QuantType.QInt8)
        return True
    except Exception as exc:  # noqa: BLE001 — 버전 불일치 등은 목 경로로 흡수
        logger.warning("quantize_dynamic 실패(%s: %s) — 목(mock) 경로로 대체한다", type(exc).__name__, exc)
        return False


def benchmark_session(model_path: Path, hidden: int = HIDDEN, n_runs: int = N_RUNS) -> float:
    """onnxruntime.InferenceSession으로 평균 추론 시간(ms)을 측정한다."""
    import onnxruntime as ort

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    x = np.random.default_rng(0).standard_normal((1, hidden), dtype=np.float32)

    for _ in range(3):  # 워밍업
        session.run(None, {input_name: x})

    start = time.perf_counter()
    for _ in range(n_runs):
        session.run(None, {input_name: x})
    elapsed_ms = (time.perf_counter() - start) / n_runs * 1000
    return elapsed_ms


def main() -> None:
    build_toy_reranker(FP32_PATH)
    fp32_size_mb = FP32_PATH.stat().st_size / (1024 * 1024)
    fp32_latency_ms = benchmark_session(FP32_PATH)
    logger.info("fp32 축소 모델: 크기 %.2fMB, 평균 추론 %.2fms", fp32_size_mb, fp32_latency_ms)

    quantized = try_quantize_dynamic(FP32_PATH, INT8_PATH)

    if quantized and INT8_PATH.exists():
        int8_size_mb = INT8_PATH.stat().st_size / (1024 * 1024)
        int8_latency_ms = benchmark_session(INT8_PATH)
        mode = "실제 quantize_dynamic 적용"
    else:
        # 이 환경에서 quantize_dynamic을 쓸 수 없을 때: 실측 비율(크기 1/4,
        # 속도 ~28% 개선)을 축소 모델 수치에 그대로 대입한 추정치다.
        # 실제로 파일을 깎아서 만들지 않는다 — 추정치임을 숨기지 않는다.
        int8_size_mb = fp32_size_mb / 4.0
        int8_latency_ms = fp32_latency_ms * (REAL_WORLD_BENCHMARK["int8"]["latency_ms"] / REAL_WORLD_BENCHMARK["fp32"]["latency_ms"])
        mode = "추정치 (이 환경은 quantize_dynamic 미지원 — 실측 비율을 대입)"

    print(f"\n[축소 모델 비교 — {mode}]")
    print(f"{'':<10} {'크기(MB)':>12} {'추론(ms)':>12}")
    print("-" * 36)
    print(f"{'fp32':<10} {fp32_size_mb:>12.2f} {fp32_latency_ms:>12.2f}")
    print(f"{'int8':<10} {int8_size_mb:>12.2f} {int8_latency_ms:>12.2f}")
    print(f"크기 비율: fp32의 {int8_size_mb / fp32_size_mb:.2f}배")
    print(f"속도 비율: fp32 대비 {(1 - int8_latency_ms / fp32_latency_ms) * 100:.1f}% 개선")

    print("\n[실제 운영 리랭커 실측값 — 이 스크립트로 재현 불가, 인용만]")
    print(f"{'':<10} {'정확도':>10} {'추론(ms)':>10} {'크기(GB)':>10}")
    print("-" * 44)
    for tag, row in REAL_WORLD_BENCHMARK.items():
        print(f"{tag:<10} {row['accuracy']*100:>9.1f}% {row['latency_ms']:>10} {row['size_gb']:>10.2f}")
    acc_drop = (REAL_WORLD_BENCHMARK["fp32"]["accuracy"] - REAL_WORLD_BENCHMARK["int8"]["accuracy"]) * 100
    print(f"\n주의: 속도는 빨라지고 크기는 줄었지만, 정확도는 {acc_drop:.1f}%p 떨어졌다.")
    print("'성능이 좋아졌다'는 말을 쓸 때 정확도인지 속도인지 반드시 구분해야 한다.")


if __name__ == "__main__":
    main()
