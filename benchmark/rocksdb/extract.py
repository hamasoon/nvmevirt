import re
import os
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# BENCHMARK 리스트와 MAPPING 리스트 정의 (Origin은 별도)
BENCHMARK = [
    "IMMEDIATE", "FULL_SINGLE", "FULL_DOUBLE", "FULL_QUATER",
    "FULL_HALF", "FULL_ALL", "WATERMARK_NAIVE", "WATERMARK_HIGHLOW"
]
MAPPING = ["4k", "16k", "32k"]

def extract_compaction_metrics(lines):
    """
    ** Compaction Stats [default] ** 섹션에서
    각 레벨별로 "Rd(MB/s)", "Wr(MB/s)", "Comp(sec)", "W-Amp" 값을 추출한다.
    단, "Size" 열이 두 토큰으로 분리되는 문제를 해결하였다.
    """
    metrics = []
    pattern_section = re.compile(r"\*\*\s*Compaction Stats \[default\]\s*\*+")
    i = 0
    while i < len(lines):
        line = lines[i]
        if pattern_section.search(line):
            # 헤더 행 ("Level" 포함) 찾기
            j = i + 1
            while j < len(lines) and "Level" not in lines[j]:
                j += 1
            if j < len(lines):
                header_line = lines[j].strip()
                header_tokens = header_line.split()
                # 구분선(---) 건너뛰기
                j += 1
                while j < len(lines) and lines[j].strip() and not lines[j].startswith("**"):
                    row_line = lines[j].strip()
                    row_tokens = row_line.split()
                    # "Size" 열이 두 토큰으로 분리된 경우 처리
                    if len(row_tokens) == len(header_tokens) + 1:
                        row_tokens = row_tokens[:2] + [" ".join(row_tokens[2:4])] + row_tokens[4:]
                    if len(row_tokens) >= len(header_tokens):
                        row_dict = dict(zip(header_tokens, row_tokens))
                        entry = {
                            'Level': row_dict.get('Level', ''),
                            'Rd(MB/s)': row_dict.get('Rd(MB/s)', ''),
                            'Wr(MB/s)': row_dict.get('Wr(MB/s)', ''),
                            'Comp(sec)': row_dict.get('Comp(sec)', ''),
                            'W-Amp': row_dict.get('W-Amp', '')
                        }
                        metrics.append(entry)
                    j += 1
            i = j
        else:
            i += 1
    return metrics

def extract_data(filename):
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    compaction_metrics = extract_compaction_metrics(lines)
    # Sum 레벨 데이터 중 마지막 행 사용
    sum_metrics = [m for m in compaction_metrics if m['Level'] == 'Sum']
    return sum_metrics[-1]

def parse_index(idx):
    """
    예: "FULL_SINGLE_4k" -> ("FULL_SINGLE", "4k")
        "WATERMARK_NAIVE_16k" -> ("WATERMARK_NAIVE", "16k")
    맨 뒤 토큰을 매핑으로, 나머지를 벤치마크로 처리한다.
    """
    parts = idx.split("_")
    mapping = parts[-1]
    benchmark = "_".join(parts[:-1])
    return benchmark, mapping

if __name__ == "__main__":
    # 1) 각 로그 파일에서 데이터 추출하여 DataFrame 생성 (원본 데이터)
    data = pd.DataFrame(columns=['Rd(MB/s)', 'Wr(MB/s)', 'Comp(sec)', 'W-Amp'])
    for benchmark in BENCHMARK:
        for mapping in MAPPING:
            idx = f"{benchmark}_{mapping}"
            filename = f"{benchmark}/{mapping}.log"
            result = extract_data(filename)
            data.loc[idx] = [
                result['Rd(MB/s)'],
                result['Wr(MB/s)'],
                result['Comp(sec)'],
                result['W-Amp']
            ]
    # Origin 로그 파일의 데이터 추출 (인덱스 "Origin")
    origin_result = extract_data(os.path.join(os.path.dirname(__file__), "origin.log"))
    data.loc['Origin'] = [
        origin_result['Rd(MB/s)'],
        origin_result['Wr(MB/s)'],
        origin_result['Comp(sec)'],
        origin_result['W-Amp']
    ]
    
    # 2) 데이터 타입 float 변환 (raw 데이터)
    data = data.astype(float)
    
    # 3) Origin을 포함하는 DataFrame 생성: 인덱스에서 Benchmark와 Mapping 정보 추가
    # Origin의 경우, Benchmark는 "Origin", Mapping은 빈 문자열("")
    df = data.copy()
    df["Benchmark"], df["Mapping"] = zip(*[
        ("Origin", "") if idx == "Origin" else parse_index(idx) for idx in df.index
    ])
    # x축 순서는 BENCHMARK 순서 + "Origin"을 마지막에 추가
    unique_benchmarks = BENCHMARK + ["Origin"]
    
    # 4) 각 성능 지표별로 2×2 subplot 생성 (raw data 사용)
    metrics = ['Rd(MB/s)', 'Wr(MB/s)', 'Comp(sec)', 'W-Amp']
    color_dict = {"4k": "skyblue", "16k": "lightgreen", "32k": "orange"}
    width = 0.2  # bar 폭
    x = np.arange(len(unique_benchmarks))  # x축 위치: 각 그룹별(benchmark)
    
    # 그래프 크기를 크게 조정 (너비, 높이)
    fig, axs = plt.subplots(2, 2, figsize=(24, 14))
    axs = axs.flatten()
    
    for i, metric in enumerate(metrics):
        ax = axs[i]
        origin_val = data.loc['Origin', metric]
        
        for j, bench in enumerate(unique_benchmarks):
            if bench == "Origin":
                # Origin은 mapping 분리 없이 단일 bar
                row = df[df["Benchmark"] == "Origin"]
                val = row[metric].values[0] if not row.empty else 0.0
                origin_bar = ax.bar(j, val, width, color='gray', label="Origin" if j == len(unique_benchmarks)-1 else "")

            else:
                # 나머지 Benchmark: 각 mapping에 대해 bar를 그림
                for k, mapping in enumerate(MAPPING):
                    offset = (k - (len(MAPPING) - 1) / 2) * width
                    row = df[(df["Benchmark"] == bench) & (df["Mapping"] == mapping)]
                    val = row[metric].values[0] if not row.empty else 0.0
                    bars = ax.bar(
                        j + offset, 
                        val, 
                        width, 
                        color=color_dict.get(mapping, 'gray'),
                        label=mapping.capitalize() if j == 0 else ""
                    )
                    
                    # 비율 계산 후 소수점 둘째 자리에서 반올림
                    ratio = 0.0
                    if origin_val != 0:
                        ratio = round((val / origin_val) * 100, 2)
                    
                    # 텍스트 표시 (회전 + 약간 위로)
                    for bar in bars:
                        bar_height = bar.get_height()
                        bar_xcenter = bar.get_x() + bar.get_width()/2
                        ax.text(
                            bar_xcenter, 
                            bar_height - len(f"{ratio}%") * 0.02 * bar_height, 
                            f"{ratio}%", 
                            ha='center', va='bottom', 
                            fontsize=8,       # 조금 작은 폰트
                            rotation=270       # 세로로 표시
                        )
        
        # Origin의 raw 값에 해당하는 빨간 점선
        ax.axhline(origin_val, color='red', linestyle='--', linewidth=1, label="Origin Value")
        ax.set_title(f'{metric} (Raw Data)', fontsize=14)
        ax.set_ylabel('Raw Value', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(unique_benchmarks, rotation=45, fontsize=11)
        ax.legend(title="Mapping", loc="lower right", fontsize=10)
    
    plt.tight_layout()
    output_path = os.path.join(os.path.dirname(__file__), "result.png")
    plt.savefig(output_path, bbox_inches="tight", dpi=300)