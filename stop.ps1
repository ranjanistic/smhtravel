# Define the Conda environment name
$envName = "smhtravel"

# Activate the Conda environment
conda activate $envName

# Get the process ID of the uvicorn app
$process = Get-Process | Where-Object { $_.Path -like "*uvicorn*" }

# If the process is found, stop it
if ($process) {
    $process | Stop-Process
    Write-Host "FastAPI app (uvicorn) has been stopped."
} else {
    Write-Host "No running uvicorn process found."
}
