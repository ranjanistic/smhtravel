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
AIRLINES_FOLDER = 'airlines'

def extract_pages_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    pages = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pages.append(page.get_text("text"))
    return pages

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


def create_output(inputfilename,pagesData, template, base_price, airport_tax, service_tax, total_price):
    # for each page in pagesData, create a new pdf file using the template
    for i in range(len(pagesData)):
        reader = PdfReader(template)
        writer = PdfWriter()
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.drawString(100, 380, base_price)
        can.drawString(100, 365, airport_tax)
        can.drawString(100, 350, service_tax)
        can.drawString(100, 335, total_price)
        can.save()
        packet.seek(0)

        overlay_pdf = PdfReader(packet)
        page = reader.pages[0]
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)
        if len(pagesData) > 1:
            with open(os.path.join(OUTPUT_FOLDER,f"new-{inputfilename}-{i}.pdf"), 'wb') as output_pdf:
                writer.write(output_pdf)
        else:
            with open(os.path.join(OUTPUT_FOLDER,f"new-{inputfilename}.pdf"), 'wb') as output_pdf:
                writer.write(output_pdf)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    temps = [f for f in os.listdir(TEMPLATES_FOLDER) if f.lower().endswith('.pdf') and os.path.isfile(os.path.join(TEMPLATES_FOLDER, f))]
    airlines = [f for f in os.listdir(AIRLINES_FOLDER) if f.lower().endswith('.png') or f.lower().endswith('.jpg')  and os.path.isfile(os.path.join(AIRLINES_FOLDER, f))]
    outputs = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith('.pdf') and f.lower().startswith('new-') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    # for each file, set the output file if name is new-{file}
    for file in files:
        if f"new-{file}" in outputs or len(list(filter(lambda x: x.startswith(f"new-{file.replace('.pdf','')}"), outputs))):
            files[files.index(file)] = (file, f"new-{file}")
        else:
            files[files.index(file)] = (file, None)
    
    return templates.TemplateResponse("index.html", dict(request=request, files=files, templates=temps, airlines=airlines))



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
        pages = extract_pages_from_pdf(os.path.join(UPLOAD_FOLDER,file['name']))
        create_output(file['name'].replace('.pdf',''), pages, os.path.join(TEMPLATES_FOLDER,file['template']), file['base_price'], file['airport_tax'], file['service_tax'], file['total_price'])
        # print(filedata)
        # write_on_pdf(os.path.join(UPLOAD_FOLDER,file['name']),os.path.join(OUTPUT_FOLDER,f"new-{file['name']}"), filedata, 100, 100, 0)
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
        files = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith('.pdf') and f.startswith(f"{file_name.replace('.pdf','')}")]
        print(files, file_name,f"{file_name.replace('.pdf','')}")
        if files:
            zip_file_path = f"{file_name}.zip"
            # create a separate folder and copy the files there
            for file in files:
                if not os.path.exists(os.path.join(OUTPUT_FOLDER, file_name.replace('.pdf',''))):
                    os.mkdir(os.path.join(OUTPUT_FOLDER, file_name.replace('.pdf','')))
                shutil.copyfile(os.path.join(OUTPUT_FOLDER, file), os.path.join(OUTPUT_FOLDER, file_name.replace('.pdf',''), file.replace(f"new-{file_name.replace('.pdf','')}",'')))
            
            shutil.make_archive(file_name, "zip", os.path.join(OUTPUT_FOLDER, file_name.replace('.pdf','')))
            
            shutil.rmtree(os.path.join(OUTPUT_FOLDER, file_name.replace('.pdf','')))
            return FileResponse(
                f"{file_name}.zip",
                media_type="application/zip",
                filename=f"{file_name}.zip",
            )
        return JSONResponse(jsonable_encoder(dict(message= "File not found.")), status_code=404) 
    
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
