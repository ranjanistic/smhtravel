@echo off

:: Define the Conda environment name
set ENV_NAME=smhtravel

:: Start the FastAPI app with uvicorn in the background
start /B conda run -n %ENV_NAME% uvicorn app:app --host localhost --port 8000

echo FastAPI app is now running in the background using uvicorn.
