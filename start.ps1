# Define the Conda environment name
$envName = "smhtravel"

# Activate the Conda environment
conda activate $envName

# Start the FastAPI app with uvicorn in the background
Start-Process -NoNewWindow -FilePath "conda" -ArgumentList "run", "-n", $envName, "uvicorn", "app:app", "--host", "localhost", "--port", "8000"

Write-Host "FastAPI app is now running in the background using uvicorn."
