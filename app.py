import shutil
import time
from fastapi.encoders import jsonable_encoder
import fitz
import re
import os
from thefuzz import fuzz, process
# from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import dateutil.parser

app = FastAPI()

# Set up templates folder
templates = Jinja2Templates(directory="web")
TEMPLATES_FOLDER = 'template'
UPLOAD_FOLDER = 'input'
OUTPUT_FOLDER = 'output'
AIRLINES_FOLDER = 'airlines'

def find_index_with_prefix(string_list, prefix):
    try:
        return next(i for i, s in enumerate(string_list) if (lambda x: x.startswith(prefix))(s))
    except StopIteration:
        return -1

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


def getTicketTypeFromRawData(rawdata):
    print(rawdata)
    if rawdata[0].strip() == 'This document is not valid for traveling':
        return 1
    if rawdata[0].strip() == 'Cancellation penalties:':
        return 2
    if rawdata[0].strip() == 'Airline':
        return 3
    if 'Passport Expire Date' in rawdata:
        return 4
    if 'RESERVATION CONFIRMED' in rawdata or '• TRAVEL SEGMENTS' in rawdata:
        return 5
    
    return False

def getRawDataFromPageData(pageData):
    print(pageData)
    return  list(filter(lambda x: len(x) > 0 ,list(map(lambda y: y.strip(), pageData.replace(u'\xa0', u' ').replace('’','\'').split('\n')))))

def getTicketDataFromPageData(pageData):
    rawdata = getRawDataFromPageData(pageData)
    ticketType = getTicketTypeFromRawData(rawdata)
    if not ticketType:
        return None
    default_value = '-'
    data = dict(ticketType=ticketType, rawdata=rawdata)
    if ticketType == 1:

        data['traveller'] = rawdata[rawdata.index('Traveler:')+1].upper() or default_value
        data['passport_no'] = default_value
        data['dob'] = default_value
        
        data['airline_name'] = rawdata[rawdata.index('Airline')+6] or default_value
        data['status'] = rawdata[rawdata.index('Status')+5].upper() or default_value
        data['flight_no'] = rawdata[rawdata.index('Flight No')+5].split(' ').pop() or default_value
        data['cabin'] = rawdata[rawdata.index('Cabin/Class')+5] or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[[i for i, x in enumerate(rawdata) if 'Airline PNR:' in x][0]].split(':')[1] or default_value
        data['ticket_no'] = default_value
        data['depart'] = rawdata[rawdata.index('Depart')+1] or default_value
        data['arrive'] = rawdata[rawdata.index('Arrive')+1] or default_value
        data['date'] =  str(dateutil.parser.parse(" ".join(rawdata[rawdata.index('Date')+6].split(' ')[0:3])).date()) or default_value
        data['time'] = rawdata[rawdata.index('Time')+1] or default_value
        data['baggage'] = rawdata[rawdata.index('Baggage')+5] or default_value
        data['departure_terminal'] = default_value
        
        isReturnTrip = len([i for i, x in enumerate(rawdata) if x == "Depart"]) > 1
        data['isReturnTrip'] = isReturnTrip

        if isReturnTrip:
            data['airline_name2'] = rawdata[[i for i, x in enumerate(rawdata) if x == "Airline"][1]+6] or default_value
            # data['status2'] = rawdata[[i for i, x in enumerate(rawdata) if x == "Status"][1]+5] or default_value
            data['flight_no2'] = rawdata[[i for i, x in enumerate(rawdata) if x == 'Flight No'][1]+5].split(' ').pop() or default_value
            data['cabin2'] = rawdata[[i for i, x in enumerate(rawdata) if x == 'Cabin/Class'][1]+5] or default_value
            data['stop2'] = default_value
            data['airline_pnr2'] = rawdata[[i for i, x in enumerate(rawdata) if 'Airline PNR:' in x][1]].split(':')[1] or default_value
            data['ticket_no2'] = default_value
            data['depart2'] = rawdata[[i for i, x in enumerate(rawdata) if x == "Depart"][1]+1] or default_value
            data['arrive2'] = rawdata[[i for i, x in enumerate(rawdata) if x == "Arrive"][1]+1] or default_value
            data['date2'] = str(dateutil.parser.parse(" ".join(rawdata[[i for i, x in enumerate(rawdata) if x == "Date"][3]+6].split(' ')[0:3])).date()) or default_value
            data['time2'] = rawdata[[i for i, x in enumerate(rawdata) if x == "Time"][2]+1] or default_value
            data['baggage2'] = rawdata[[i for i, x in enumerate(rawdata) if x == "Baggage"][1]+5] or default_value
            data['departure_terminal2'] = default_value
    elif ticketType == 2:
        traveller = rawdata[rawdata.index('Passenger Name')+3].upper() or default_value
        data['traveller'] = traveller.split('/')[1].split("-")[0].strip()+" "+ traveller.split('/')[0].replace("_"," ")
        data['passport_no'] = rawdata[rawdata.index('Passport No / National ID')+1] or default_value
        data['dob'] = default_value
        
        data['airline_name'] = rawdata[rawdata.index('Cancellation penalties:')+8] or default_value
        data['status'] = default_value
        data['flight_no'] = data['airline_name'].split(' ')[0] or default_value
        data['cabin'] = rawdata[rawdata.index('Class')+1].split(" ")[0] or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[rawdata.index('Local PNR')+1] or default_value
        data['ticket_no'] = rawdata[rawdata.index('Ticket number')+3] or default_value
        data['depart'] = rawdata[rawdata.index('Origin')-5] or default_value
        data['arrive'] = rawdata[rawdata.index('Destination')-5] or default_value
        data['date'] =  str(dateutil.parser.parse(" ".join(rawdata[rawdata.index('Flight Date')-5].split(" ")[1:])).date()) or default_value
        data['time'] = rawdata[rawdata.index('Flight time')-5] or default_value
        data['baggage'] = rawdata[rawdata.index('Checked Baggage')+5].split(' ')[2]+' KG' or default_value
        data['departure_terminal'] = default_value
        
        isReturnTrip = len([i for i, x in enumerate(rawdata) if x == "Origin"]) > 1
        data['isReturnTrip'] = isReturnTrip
    elif ticketType == 3:
        data['traveller'] = " ".join(list(filter(lambda x: x.strip(), rawdata[find_index_with_prefix(rawdata,'Traveler:')].split(' ')))[1:]) or default_value
        data['passport_no'] = default_value
        data['dob'] = default_value
        
        data['airline_name'] = list(filter(lambda x: x.strip(),re.split("  ",rawdata[rawdata.index('Airline')+11])))[0] or default_value
        data['status'] = default_value
        data['flight_no'] = list(filter(lambda x: x.strip(),re.split("  ",rawdata[rawdata.index('Airline')+11])))[1] or default_value
        data['cabin'] = list(filter(lambda x: x.strip(),re.split("  ",rawdata[rawdata.index('Airline')+11])))[2].split("/")[0].strip() or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[[i for i, x in enumerate(rawdata) if 'Airline PNR:' in x][0]].split(':')[1] or default_value
        data['ticket_no'] = rawdata[find_index_with_prefix(rawdata,'E-Ticket Number:')].split(":")[1].strip() or default_value
        data['depart'] = rawdata[find_index_with_prefix(rawdata,'Depart:')].split(":")[1].strip() or default_value
        data['arrive'] = rawdata[find_index_with_prefix(rawdata,'Arrive:')].split(":")[1].strip() or default_value
        data['date'] =  str(dateutil.parser.parse(rawdata[[i for i, x in enumerate(rawdata) if x.startswith("Date:")][0]].split("Time:")[0].split(":")[1].strip()).date()) or default_value
        data['time'] =  rawdata[[i for i, x in enumerate(rawdata) if x.startswith("Date:")][0]].split("Time:")[1].strip() or default_value
        data['baggage'] = "".join(list(filter(lambda x: x.strip(),re.split("  ",rawdata[rawdata.index('Airline')+11])))[2].split("/")[1].split(" ")[3:]).strip() or default_value
        data['departure_terminal'] =  rawdata[find_index_with_prefix(rawdata,"Departure Terminal:")].split(":")[1].strip() or default_value
        
        isReturnTrip = len([i for i, x in enumerate(rawdata) if x.startswith("Depart:")]) > 1
        data['isReturnTrip'] = isReturnTrip
    elif ticketType == 4:
        data['traveller'] = rawdata[rawdata.index('Passenger\'s Name')+1].upper() or default_value
        data['passport_no'] = rawdata[rawdata.index('Passport Number')+1].upper() or default_value
        data['dob']= default_value
        
        data['airline_name'] = rawdata[rawdata.index('Airline:')+1] or default_value
        data['status'] = default_value
        data['flight_no'] = rawdata[find_index_with_prefix(rawdata,'Flight Number:')].split(":")[1] or default_value
        data['cabin'] = rawdata[rawdata.index('Cabin Class:')+1] or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[rawdata.index('Airline reservation code (PNR):')+1] or default_value
        data['ticket_no'] = rawdata[rawdata.index('Ticket Number:')+1] or default_value
        data['depart'] = rawdata[rawdata.index('Origin')+1] or default_value
        data['arrive'] = rawdata[rawdata.index('Destination')+1] or default_value
        data['date'] = str(dateutil.parser.parse(rawdata[rawdata.index('Origin')+3]).date()) or default_value
        data['time'] = rawdata[rawdata.index('Origin')+4].split(" ")[1] or default_value
        data['baggage'] = rawdata[rawdata.index('Checked-in baggage')+1] or default_value
        data['departure_terminal'] = default_value
        data['isReturnTrip'] = False
    elif ticketType == 5:
        pass
    return data



def create_output(inputfilename, pagesData, base_price, airport_tax, service_tax, total_price, logo=None):
    skip_pages = []
    for i in range(len(pagesData)):
        if i in skip_pages:
            continue
        ticket = getTicketDataFromPageData(pagesData[i])
        if not ticket:
            continue
        # print(ticket)
        if ticket['ticketType'] == 4 and len(pagesData)-1 >= i+1:
            ticket2 = getTicketDataFromPageData(pagesData[i+1])
            if ticket2['passport_no'] == ticket['passport_no'] and ticket2['depart'] == ticket['arrive'] and ticket2['arrive'] == ticket['depart']:
                ticket['isReturnTrip'] = True
                ticket['airline_name2'] = ticket2['airline_name']
                ticket['flight_no2'] = ticket2['flight_no']
                ticket['cabin2'] = ticket2['cabin']
                ticket['stop2'] = ticket2['stop']
                ticket['airline_pnr2'] = ticket2['airline_pnr']
                ticket['ticket_no2'] = ticket2['ticket_no']
                ticket['depart2'] = ticket2['depart']
                ticket['arrive2'] = ticket2['arrive']
                ticket['date2'] = ticket2['date']
                ticket['time2'] = ticket2['time']
                ticket['baggage2'] = ticket2['baggage']
                ticket['departure_terminal2'] = ticket2['departure_terminal']
                skip_pages.append(i+1)
        if ticket['ticketType'] == 5 and 'RESERVATION CONFIRMED' in ticket['rawdata']:
            ticket2 = getTicketDataFromPageData(pagesData[i+1])
            


        template = os.path.join(TEMPLATES_FOLDER, '2.pdf' if ticket['isReturnTrip'] else '1.pdf') 
        reader = PdfReader(template)
        writer = PdfWriter()
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.setFontSize(8)
        # check if airline logo exists

        can.drawString(10, 622, ticket['traveller'])
        can.drawString(230, 622, ticket['passport_no'])
        can.drawString(350, 622, ticket['dob'])
        can.drawString(435, 622, ticket['status'])

        can.drawString(50, 475, ticket['airline_name'])
        if not logo:
            logo,_ = process.extractOne(ticket['airline_name'], os.listdir(AIRLINES_FOLDER))
        else:
            logo,_ = process.extractOne(logo, os.listdir(AIRLINES_FOLDER))
        if logo:
            can.drawImage(os.path.join(AIRLINES_FOLDER, logo), 7, 470, width=30, height=30)
        can.drawString(200, 475, ticket['flight_no'])
        can.drawString(290, 475,ticket['cabin'])
        can.drawString(360,475,ticket['stop'])
        can.drawString(420,475,ticket['airline_pnr'])
        can.drawString(500,475,ticket['ticket_no'])
        
        can.drawString(150, 460,ticket['depart'])
        can.drawString(150, 445,ticket['arrive'])

        can.drawString(290, 445,ticket['date'])
        can.drawString(360,445,ticket['time'])
        can.drawString(420,445,ticket['baggage'])
        can.drawString(500,445,ticket['departure_terminal'])


        if not ticket['isReturnTrip']:
            can.drawString(100, 382, base_price)
            can.drawString(100, 367, airport_tax)
            can.drawString(100, 352, service_tax)
            can.drawString(100, 337, total_price)
        else:
            can.drawString(40, 385, ticket['airline_name2'])
            if not logo:
                logo,_ = process.extractOne(ticket['airline_name2'], os.listdir(AIRLINES_FOLDER))
            else:
                logo,_ = process.extractOne(logo, os.listdir(AIRLINES_FOLDER))
            if logo:
                can.drawImage(os.path.join(AIRLINES_FOLDER, logo), 7, 380, width=30, height=30)
            can.drawString(200,385, ticket['flight_no2'])
            can.drawString(290,385,ticket['cabin2'])
            can.drawString(360,385,ticket['stop2'])
            can.drawString(420,385,ticket['airline_pnr2'])
            can.drawString(500,385,ticket['ticket_no2'])

            can.drawString(150, 370,ticket['depart2'])
            can.drawString(150,355,ticket['arrive2'])

            can.drawString(290,355,ticket['date2'])
            can.drawString(360,355,ticket['time2'])
            can.drawString(420,355,ticket['baggage2'])
            can.drawString(500,355,ticket['departure_terminal2'])

            can.drawString(95, 285, base_price)
            can.drawString(95, 270, airport_tax)
            can.drawString(95, 255, service_tax)
            can.drawString(95, 240, total_price)
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
    airlines = [f.capitalize() for f in os.listdir(AIRLINES_FOLDER) if f.lower().split(".")[-1:][0] in ['png','jpg','jpeg'] and os.path.isfile(os.path.join(AIRLINES_FOLDER, f))]
    airlines.sort()
    outputs = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith('.pdf') and f.lower().startswith('new-') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    # for each file, set the output file if name is new-{file}
    for file in files:
        if f"new-{file}" in outputs or len(list(filter(lambda x: x.startswith(f"new-{file.replace('.pdf','')}"), outputs))):
            files[files.index(file)] = (file, f"new-{file}")
        else:
            files[files.index(file)] = (file, None)
    
    return templates.TemplateResponse("index.html", dict(request=request, files=files, templates=temps, airlines=airlines))

@app.get("/history", response_class=HTMLResponse)
async def index(request: Request):
    outputs = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith('.pdf') and f.lower().startswith('new-') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    return templates.TemplateResponse("output.html", dict(request=request, outputs=outputs))



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
                      airline=body['airline'],
                      )]
    else:
        files = body
    for file in files:
        pages = extract_pages_from_pdf(os.path.join(UPLOAD_FOLDER,file['name']))
        create_output(file['name'].replace('.pdf',''), pages, file['base_price'], file['airport_tax'], file['service_tax'], file['total_price'], file.get('airline',None))
    
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
