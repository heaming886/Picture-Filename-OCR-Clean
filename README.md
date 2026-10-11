# Picture Filename OCR Clean

用 RapidOCR 辨識圖片上半部文字來命名圖片，並提供檔名清理工具：移除指定字詞、分割黏在一起的英文單字。

## 環境安裝

建議使用 64 位元 Python 3.12：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## OCR 命名

先預覽（預設上半部 50%）：

```powershell
.venv\Scripts\python.exe rename_by_ocr.py . --top 0.5
```

確認預覽後加上 `--apply` 執行改名。可用 `--recursive` 遞迴子目錄，也可用 `--prefix` 指定沒有辨識到文字時的檔名。

## 清理檔名

預覽移除指定字詞並修整英文單字：

```powershell
.venv\Scripts\python.exe clean-word.py . --remove Taiz Telecom Academy
```

預設只預覽；加上 `--apply` 才會改名。也可用 `--remove-file delete-word.txt` 讀取每行一個移除詞，並用 `--recursive` 包含子目錄。
