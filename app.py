import shutil
from fastapi.encoders import jsonable_encoder
import fitz
import os
# from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Set up templates folder
templates = Jinja2Templates(directory="web")
TEMPLATES_FOLDER = 'template'
UPLOAD_FOLDER = 'input'
OUTPUT_FOLDER = 'output'

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text += "\n\n=====\n\n"+ page.get_text("text") 
    return text

def write_on_pdf(input_pdf_path, output_pdf_path, text, x, y, page_number=0):
    
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.drawString(x, y, text)
    can.save()
    packet.seek(0)

    overlay_pdf = PdfReader(packet)
    for i in range(len(reader.pages)):
        page = reader.pages[i]
        if i == page_number:
            page.merge_page(overlay_pdf.pages[0]) 
        writer.add_page(page)

    with open(output_pdf_path, 'wb') as output_pdf:
        writer.write(output_pdf)



@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    temps = [f for f in os.listdir(TEMPLATES_FOLDER) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(TEMPLATES_FOLDER, f))]
    outputs = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith('.pdf') and f.lower().startswith('new-') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    # for each file, set the output file if name is new-{file}
    for file in files:
        if f"new-{file}" in outputs:
            files[files.index(file)] = (file, f"new-{file}")
        else:
            files[files.index(file)] = (file, None)
    
    return templates.TemplateResponse("index.html", dict(request=request, files=files, templates=temps))



@app.post("/upload-files/", response_class=HTMLResponse)
async def upload_files(files: list[UploadFile] = File(...)):
    """Handle multiple PDF file uploads."""
    for file in files:
        if file.content_type == "application/pdf":
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        else:
            return JSONResponse(jsonable_encoder(dict(message= f"Invalid file type for {file.filename}. Only PDFs are allowed.")), status_code=400)
    return RedirectResponse(url="/", status_code=303)


@app.get("/upload-preview/", response_class=HTMLResponse)
async def upload_preview(request: Request):
    file_name = request.query_params.get('file',None)
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        return JSONResponse(jsonable_encoder(dict(message= "File not found.")), status_code=404)
       
    return FileResponse(path=file_path, media_type='application/pdf', filename=file_name)

@app.post("/upload-process/", response_class=HTMLResponse)
async def upload_process(request: Request):
    file_name = request.query_params.get('file',None)
    body = await request.json()
    if file_name:
        files = [dict(name=file_name,
                      base_price=body['base_price'],
                      airport_tax=body['airport_tax'],
                      service_tax=body['service_tax'],
                      template=body['template'],
                      total_price=body['total_price'],
                      )]
    else:
        files = body
    for file in files:
        filedata = extract_text_from_pdf(os.path.join(UPLOAD_FOLDER,file['name']))
        # print(filedata)
        write_on_pdf(os.path.join(UPLOAD_FOLDER,file['name']),os.path.join(OUTPUT_FOLDER,f"new-{file['name']}"), filedata, 100, 100, 0)
    return JSONResponse(jsonable_encoder(dict(message= "Files processed.")))



@app.delete("/upload-clear/", response_class=HTMLResponse)
async def upload_clear(request: Request):
    
    file_name = request.query_params.get('file',None)

    if file_name:
        files = [file_name]
    else:
        files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        if os.path.exists(file_path):
            os.remove(file_path)
    return JSONResponse(jsonable_encoder(dict(message= "Files cleared.")))


@app.get("/output-preview/", response_class=HTMLResponse)
async def output_preview(request: Request):
    file_name = request.query_params.get('file',None)
    if not file_name:
        zip_file_path = f"{OUTPUT_FOLDER}.zip"
        shutil.make_archive(OUTPUT_FOLDER, "zip", os.path.join(OUTPUT_FOLDER))
        return FileResponse(
            zip_file_path,
            media_type="application/zip",
            filename=f"{OUTPUT_FOLDER}.zip",
        )

    file_path = os.path.join(OUTPUT_FOLDER, file_name)
    if not os.path.exists(file_path):
       return {"error": "File not found"} 
    return FileResponse(path=file_path, media_type='application/pdf', filename=file_name)


@app.delete("/output-discard/", response_class=HTMLResponse)
async def output_discard(request: Request):
    file_name = request.query_params.get('file',None)
    if file_name:
        files = [file_name]
    else:
        files = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    for file in files:
        file_path = os.path.join(OUTPUT_FOLDER, file)
        if os.path.exists(file_path):
            os.remove(file_path)
    return JSONResponse(jsonable_encoder(dict(message= "Output cleared.")))
