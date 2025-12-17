import resource
import time
import traceback

import numpy as np
import pandas as pd
import polars as pl
import psutil

from benchmark import Benchmark


# ============================================================
# Benchmark core (multiprocessing-safe)
# ============================================================
def run_in_process(func, args, kwargs, return_dict):
    # Polars multiprocessing safety 설정
    import polars as pl
    try:
        # Polars가 multiprocessing에서 안전하게 동작하도록 설정
        pl.Config.set_engine_affinity('single')  # 싱글 스레드 엔진 사용
        pl.Config.set_streaming_chunk_size(1000)  # 스트리밍 청크 크기 제한
    except Exception:
        pass  # Config 설정 실패해도 계속 진행

    start = time.perf_counter()

    try:
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        try:
            peak_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception:
            peak_mem = psutil.Process().memory_info().rss

        return_dict["success"] = True
        return_dict["time"] = elapsed
        return_dict["memory"] = peak_mem
        return_dict["result"] = result

    except Exception as e:
        return_dict["success"] = False
        return_dict["error"] = str(e)
        return_dict["traceback"] = traceback.format_exc()

# ============================================================
# Data generators (각 테스트 함수 내부에서 사용)
# ============================================================
def generate_pandas_df(n_rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "id": np.arange(n_rows),
        "category": rng.choice(["A", "B", "C", "D"], size=n_rows),
        "value1": rng.normal(size=n_rows),
        "value2": rng.integers(0, 1000, size=n_rows),
        "text": rng.choice(["foo", "bar", "baz"], size=n_rows),
    })


def generate_polars_df(n_rows: int) -> pl.DataFrame:
    rng = np.random.default_rng(42)
    return pl.DataFrame({
        "id": np.arange(n_rows),
        "category": rng.choice(["A", "B", "C", "D"], size=n_rows),
        "value1": rng.normal(size=n_rows),
        "value2": rng.integers(0, 1000, size=n_rows),
        "text": rng.choice(["foo", "bar", "baz"], size=n_rows),
    })


# ============================================================
# I/O benchmarks (Polars, multiprocessing-safe)
# ============================================================
def polars_create_only(n_rows: int):
    # DF 생성만 (결과는 버림)
    _ = generate_polars_df(n_rows)


def polars_save_only(path: str, n_rows: int):
    # 프로세스 내부에서 DF 생성 + 저장
    df = generate_polars_df(n_rows)
    df.write_parquet(path)


def polars_load_only(path: str):
    _ = pl.read_parquet(path)


# ============================================================
# Pandas operations (연산만, DF는 함수 내부에서 생성)
# ============================================================
def pandas_groupby_only(n_rows: int):
    df = generate_pandas_df(n_rows)
    _ = df.groupby("category")["value1"].agg(["mean", "sum", "count"])


def pandas_join_only(n_rows: int):
    df_left = generate_pandas_df(n_rows)
    df_right = generate_pandas_df(n_rows)
    _ = df_left.merge(df_right, on="id")


def pandas_filter_only(n_rows: int):
    df = generate_pandas_df(n_rows)
    _ = df[df["value2"] > 500]


def pandas_sort_only(n_rows: int):
    df = generate_pandas_df(n_rows)
    _ = df.sort_values(["category", "value2"])


def pandas_window_only(n_rows: int):
    df = generate_pandas_df(n_rows)
    _ = df.assign(roll=df["value1"].rolling(10, min_periods=1).mean())


# ============================================================
# Polars eager operations (연산만, DF는 함수 내부에서 생성)
# ============================================================
def polars_groupby_only(n_rows: int):
    df = generate_polars_df(n_rows)
    _ = df.group_by("category").agg([
        pl.col("value1").mean().alias("mean"),
        pl.col("value1").sum().alias("sum"),
        pl.col("value1").count().alias("count"),
    ])


def polars_join_only(n_rows: int):
    df_left = generate_polars_df(n_rows)
    df_right = generate_polars_df(n_rows)
    _ = df_left.join(df_right, on="id")


def polars_filter_only(n_rows: int):
    df = generate_polars_df(n_rows)
    _ = df.filter(pl.col("value2") > 500)


def polars_sort_only(n_rows: int):
    df = generate_polars_df(n_rows)
    _ = df.sort(["category", "value2"])


def polars_window_only(n_rows: int):
    df = generate_polars_df(n_rows)
    _ = df.sort("id").with_columns(
        pl.col("value1").rolling_mean(10).alias("roll")
    )


# ============================================================
# Polars lazy operations (Parquet 기반, path만 인자로 사용)
# ============================================================
def polars_lazy_groupby_only(path: str):
    _ = (
        pl.scan_parquet(path)
        .group_by("category")
        .agg(pl.col("value1").mean().alias("mean"))
        .collect()
    )


def polars_lazy_filter_only(path: str):
    _ = (
        pl.scan_parquet(path)
        .filter(pl.col("value2") > 500)
        .collect()
    )


def polars_lazy_sort_only(path: str):
    _ = (
        pl.scan_parquet(path)
        .sort("value2")
        .collect()
    )


def polars_lazy_join_only(path_left: str, path_right: str):
    left = pl.scan_parquet(path_left)
    right = pl.scan_parquet(path_right)
    _ = left.join(right, on="id").collect()


# ============================================================
# Main benchmark
# ============================================================
if __name__ == "__main__":
    sizes = [1_000_000, 5_000_000]
    bench = Benchmark(repeat=3, modules=["pandas", "polars"])

    for n in sizes:
        print(f"\n===== Benchmark for {n:,} rows =====")

        # 미리 저장해둘 Parquet 파일 경로 (lazy에서 사용)
        path_main = f"data_main_{n}.parquet"
        path_join = f"data_join_{n}.parquet"

        # 메인 프로세스에서 한 번만 생성 & 저장 (lazy 테스트용)
        df_pl_main = generate_polars_df(n)
        df_pl_join = generate_polars_df(n)
        df_pl_main.write_parquet(path_main)
        df_pl_join.write_parquet(path_join)

        # ----------------------------------------------------
        # I/O: Create / Save / Load (Polars)
        # ----------------------------------------------------
        bench.run_test(f"Polars Create ({n})", polars_create_only, n)
        bench.run_test(f"Polars Save ({n})", polars_save_only, path_main, n)
        bench.run_test(f"Polars Load ({n})", polars_load_only, path_main)

        # ----------------------------------------------------
        # Pandas operations
        # ----------------------------------------------------
        bench.run_test(f"Pandas GroupBy ({n})", pandas_groupby_only, n)
        bench.run_test(f"Pandas Join ({n})", pandas_join_only, n)
        bench.run_test(f"Pandas Filter ({n})", pandas_filter_only, n)
        bench.run_test(f"Pandas Sort ({n})", pandas_sort_only, n)
        bench.run_test(f"Pandas Window ({n})", pandas_window_only, n)

        # ----------------------------------------------------
        # Polars eager operations
        # ----------------------------------------------------
        bench.run_test(f"Polars GroupBy ({n})", polars_groupby_only, n)
        bench.run_test(f"Polars Join ({n})", polars_join_only, n)
        bench.run_test(f"Polars Filter ({n})", polars_filter_only, n)
        bench.run_test(f"Polars Sort ({n})", polars_sort_only, n)
        bench.run_test(f"Polars Window ({n})", polars_window_only, n)

        # ----------------------------------------------------
        # Polars lazy operations
        # ----------------------------------------------------
        bench.run_test(f"Polars Lazy GroupBy ({n})", polars_lazy_groupby_only, path_main)
        bench.run_test(f"Polars Lazy Filter ({n})", polars_lazy_filter_only, path_main)
        bench.run_test(f"Polars Lazy Sort ({n})", polars_lazy_sort_only, path_main)
        bench.run_test(f"Polars Lazy Join ({n})", polars_lazy_join_only, path_main, path_join)

    # 결과를 연산 유형별로 그룹화하여 비교 가능하도록 정렬
    all_results = bench.summary()

    # 결과를 연산 유형과 크기별로 그룹화
    grouped_results = {}

    for result in all_results:
        test_name = result['Test']

        # 연산 유형 추출
        if 'GroupBy' in test_name:
            op_type = 'GroupBy'
        elif 'Join' in test_name:
            op_type = 'Join'
        elif 'Filter' in test_name:
            op_type = 'Filter'
        elif 'Sort' in test_name:
            op_type = 'Sort'
        elif 'Window' in test_name:
            op_type = 'Window'
        elif 'Create' in test_name:
            op_type = 'Create'
        elif 'Save' in test_name:
            op_type = 'Save'
        elif 'Load' in test_name:
            op_type = 'Load'
        else:
            continue

        import re
        size_match = re.search(r'\((\d+)\)', test_name)
        if size_match:
            size = int(size_match.group(1))
        else:
            continue

        if 'Pandas' in test_name:
            lib_type = 'Pandas'
        elif 'Polars Lazy' in test_name:
            lib_type = 'Polars Lazy'
        elif 'Polars' in test_name:
            lib_type = 'Polars'
        else:
            continue

        key = f"{op_type} ({size})"
        if key not in grouped_results:
            grouped_results[key] = {}
        grouped_results[key][lib_type] = result

    print("\n=== System Info ===")
    print(pd.DataFrame([bench.info()]).T)

    print("\n=== Comparative Benchmark Summary ===")

    # 데이터 연산 위주로 정렬된 순서로 출력 (I/O 제외)
    operation_order = ['GroupBy', 'Join', 'Filter', 'Sort', 'Window']
    comparison_results = []

    for op in operation_order:
        for size in sizes:
            key = f"{op} ({size})"
            if key in grouped_results:
                libs = grouped_results[key]

                # Pandas, Polars, Polars Lazy 순서로 추가
                lib_order = ['Pandas', 'Polars', 'Polars Lazy']
                for lib in lib_order:
                    if lib in libs:
                        result = libs[lib].copy()
                        result['Test'] = f"{lib} {key}"
                        comparison_results.append(result)

    if comparison_results:
        df_comparison = pd.DataFrame(comparison_results)
        print(df_comparison.to_markdown(index=False))
