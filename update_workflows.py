import glob
import os

target_dir = r"c:\Users\Alan\Desktop\Stock-System\Stock-System\.agents\workflows"

append_text = """
### 輸出文件存放與驗證規範
1. **讀取前次規劃**：在開始分析前，請先讀取 `docs/` 資料夾中對應的規劃文件（如 `docs/system-review-report.md` 或 `docs/system-modification-plan.md`），以驗證前一次的修改是否已確實完成。
2. **存放本次規劃**：完成本次分析後，必須將新的分析結果與修改規劃更新或寫入至 `docs/` 資料夾中的特定文件（例如 `docs/system-modification-plan.md`）。該文件將作為下一次修改的依據。
"""

updated = 0
for fp in glob.glob(os.path.join(target_dir, "*.md")):
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "輸出文件存放與驗證規範" in content:
        continue
        
    with open(fp, "a", encoding="utf-8") as f:
        f.write(append_text)
    updated += 1

print(f"Appended output rules to {updated} workflow files.")
