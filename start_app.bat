@echo off
cd /d %~dp0
call .venv\Scripts\activate.bat

:menu
echo ==========================================
echo 入札システム 起動メニュー
echo ==========================================
echo 1. Web UI (Streamlit - app.py)
echo 2. 分析ダッシュボード (Streamlit - app_dashboard.py)
echo 3. 管理画面 (Flask - app_admin.py)
echo 4. 自動巡回クローラ (main.py)
echo 5. 終了
echo ==========================================
set /p choice="番号を選択してください (1-5): "

if "%choice%"=="1" goto run_streamlit_app
if "%choice%"=="2" goto run_streamlit_dashboard
if "%choice%"=="3" goto run_flask_admin
if "%choice%"=="4" goto run_crawler
if "%choice%"=="5" exit

echo 無効な選択です。
goto menu

:run_streamlit_app
streamlit run app.py
pause
goto menu

:run_streamlit_dashboard
streamlit run app_dashboard.py
pause
goto menu

:run_flask_admin
python app_admin.py
pause
goto menu

:run_crawler
python main.py
pause
goto menu
