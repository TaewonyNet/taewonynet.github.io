import time
import multiprocessing as mp
import traceback
import os
import pandas as pd
import resource
import psutil
import platform
import sys
import importlib
import datetime


def run_in_process(func, args, kwargs, return_dict, min_exec_time=0.0):
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["OPENBLAS_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["NUMEXPR_NUM_THREADS"] = "1"
    os.environ["POLARS_MAX_THREADS"] = "1"

    start = time.perf_counter()

    try:
        if kwargs and isinstance(kwargs, dict):
            result = func(*args, **kwargs)
        elif args:
            result = func(*args)
        else:
            result = func()

        elapsed = time.perf_counter() - start
        if elapsed < min_exec_time:
            time.sleep(min_exec_time - elapsed)

        try:
            peak_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except Exception:
            peak_mem = psutil.Process().memory_info().peak_wset

        return_dict["success"] = True
        return_dict["time"] = time.perf_counter() - start
        return_dict["memory"] = peak_mem
        return_dict["result"] = result

    except Exception as e:
        return_dict["success"] = False
        return_dict["error"] = str(e)
        return_dict["traceback"] = traceback.format_exc()


class Benchmark:
    def __init__(self, repeat=3, min_exec_time=0.0, modules=None):
        self.repeat = repeat
        self.min_exec_time = min_exec_time
        self.results = []
        self.modules = modules or []
        self.module_versions = self._load_module_versions()
        self._detail = None
        self._info = None

    def _load_module_versions(self):
        versions = {}
        for mod_name in self.modules:
            try:
                mod = importlib.import_module(mod_name)
                ver = getattr(mod, "__version__", "Unknown")
                versions[mod_name] = ver
            except Exception:
                versions[mod_name] = "Not Installed"
        return versions

    def run_test(self, label, func, *args, **kwargs):
        # Polars 함수들은 multiprocessing 없이 직접 실행 (안전성 문제 해결)
        func_name = getattr(func, '__name__', str(func))
        if 'polars' in func_name.lower():
            return self._run_test_direct(label, func, *args, **kwargs)
        else:
            return self._run_test_multiprocess(label, func, *args, **kwargs)

    def _run_test_direct(self, label, func, *args, **kwargs):
        """Polars 함수들을 직접 실행 (multiprocessing bypass)"""
        times, mems, errors = [], [], []

        for _ in range(self.repeat):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start

                try:
                    peak_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                except Exception:
                    peak_mem = psutil.Process().memory_info().rss

                times.append(elapsed)
                mems.append(peak_mem)

            except Exception as e:
                errors.append(str(e))

        if errors:
            self.results.append({
                "Test": label,
                "Time(s)": None,
                "Memory(bytes)": None,
                "Error": errors[0],
            })
        else:
            self.results.append({
                "Test": label,
                "Time(s)": round(sum(times) / len(times), 6),
                "Memory(bytes)": int(sum(mems) / len(mems)),
                "Error": None,
            })

    def _run_test_multiprocess(self, label, func, *args, **kwargs):
        """pandas 함수들은 multiprocessing으로 실행"""
        times, mems, errors = [], [], []

        manager = mp.Manager()
        warm = manager.dict()
        p = mp.Process(target=run_in_process,
                       args=(func, args, kwargs, warm, self.min_exec_time))
        p.start()
        p.join()

        for _ in range(self.repeat):
            manager = mp.Manager()
            return_dict = manager.dict()

            p = mp.Process(
                target=run_in_process,
                args=(func, args, kwargs, return_dict, self.min_exec_time)
            )
            p.start()
            p.join()

            if return_dict.get("success"):
                times.append(return_dict["time"])
                mems.append(return_dict["memory"])
            else:
                errors.append(return_dict.get("error"))

        if errors:
            self.results.append({
                "Test": label,
                "Time(s)": None,
                "Memory(bytes)": None,
                "Error": errors[0]
            })
        else:
            self.results.append({
                "Test": label,
                "Time(s)": round(sum(times) / len(times), 4),
                "Memory(bytes)": int(sum(mems) / len(mems)),
                "Error": None
            })
        return self.results[-1].get("Time(s)"), self.results[-1].get("Memory(bytes)")

    def _run_info(self):
        if not self._detail:
            cpu_freq = psutil.cpu_freq()
            load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (None, None, None)
            self._detail = {
                "Timestamp": datetime.datetime.now().isoformat(),
                "CPU_Model": platform.processor() or "Unknown",
                "CPU_Physical_Cores": psutil.cpu_count(logical=False),
                "CPU_Logical_Cores": psutil.cpu_count(logical=True),
                "CPU_Min_Freq_MHz": cpu_freq.min if cpu_freq else None,
                "CPU_Max_Freq_MHz": cpu_freq.max if cpu_freq else None,
                "CPU_Current_Freq_MHz": cpu_freq.current if cpu_freq else None,
                "Memory_Total_GB": round(psutil.virtual_memory().total / (1024 ** 3), 2),
                "Memory_Usage_Percent": psutil.virtual_memory().percent,
                "OS_Name": platform.system(),
                "OS_Release": platform.release(),
                "OS_Version": platform.version(),
                "OS_Kernel": platform.uname().release,
                "Python_Version": sys.version.split()[0],
                "Python_Build": platform.python_build(),
                "Load_Average": load_avg,
                "CPU_Usage_Percent": psutil.cpu_percent(interval=0.1),
                "Modules": self.module_versions
            }
            self._info = {
                "CPU": self._detail["CPU_Model"],
                "OS": self._detail["OS_Name"],
                "Python": self._detail["Python_Version"],
                **{f"Python_{x[0]}":x[1] for x in self._detail["Modules"].items()}
            }

    def info(self):
        self._run_info()
        return self._info

    def detail_info(self):
        self._run_info()
        return self._detail

    def summary(self):
        return self.results


def compute_sum(n):
    total = 0
    for i in range(n):
        total += i
    return total

def build_list(n):
    return [i for i in range(n)]


if __name__ == "__main__":
    bench = Benchmark(
        repeat=1,
        min_exec_time=0.01,
        modules=["pandas", "numpy", "psutil"]
    )
    print(pd.DataFrame([bench.info()]).T)

    bench.run_test("Compute Sum (5M)_1", compute_sum, 5_000_000)
    bench.run_test("Build List (3M)_1", build_list, n=3_000_000)
    bench.run_test("Compute Sum (5M)_2", compute_sum, 5_000_000)
    bench.run_test("Build List (3M)_2", build_list, n=3_000_000)
    bench.run_test("Compute Sum (5M)_3", compute_sum, 5_000_000)
    bench.run_test("Build List (3M)_3", build_list, n=3_000_000)

    print(bench.info())
    print(pd.DataFrame(bench.summary()))
