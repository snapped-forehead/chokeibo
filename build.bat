@echo off
chcp 65001 > nul
echo ========================================
echo  取引入力フォーム exe ビルド
echo ========================================
echo.

:: 仮想環境がなければ作成
if not exist ".venv" (
    echo [1/4] 仮想環境を作成中...
    python -m venv .venv
)

:: 依存パッケージをインストール
echo [2/4] パッケージをインストール中...
call .venv\Scripts\pip install -r requirements.txt --quiet

:: PyInstallerでビルド
echo [3/4] exeをビルド中（数分かかります）...
call .venv\Scripts\pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "取引入力" ^
    --add-data "templates;templates" ^
    --add-data "categories.json;." ^
    main.py

echo.
echo [4/4] 完了！
echo.
echo dist\取引入力.exe に出力されました。
echo credentials.json を dist フォルダに置いてから配布してください。
echo.
pause
