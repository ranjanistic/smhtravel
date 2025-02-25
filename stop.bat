@echo off

:: Define the Conda environment name
set ENV_NAME=smhtravel

:: Find the uvicorn process and kill it
for /f "tokens=2" %%i in ('tasklist ^| findstr "uvicorn"') do (
    echo Stopping uvicorn process with PID %%i
    taskkill /PID %%i /F
)

echo FastAPI app (uvicorn) has been stopped.
