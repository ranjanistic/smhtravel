import shutil
from fastapi.encoders import jsonable_encoder
import fitz
import re
import os
from thefuzz import process
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import dateutil.parser

app = FastAPI()

templates = Jinja2Templates(directory="web")


def hash(ke):
    return str(ke)


hashfile = "hash.data"

if not os.path.exists(hashfile):
    with open(hashfile, 'w') as f:
        f.write(str(hash('123')))

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
    pages = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pages.append(page.get_text("text"))
    return pages


def getTicketTypeFromRawData(rawdata):
    print(rawdata)
    if rawdata[0].strip() == 'This document is not valid for traveling':
        return 1
    if 'Passport No / National ID' in rawdata:
        return 2
    if rawdata[0].strip() == 'Airline':
        return 3
    if 'Passport Expire Date' in rawdata:
        return 4
    if 'RESERVATION CONFIRMED' in rawdata or 'TRAVEL SEGMENTS' in rawdata:
        return 5
    if rawdata[0].strip() == 'Electronic Ticket':
        return 6
    return False


def getRawDataFromPageData(pageData):
    return list(filter(lambda x: len(x) > 0, list(map(lambda y: y.strip(), pageData.replace(u'\xa0', u' ').replace('’', '\'').replace(u"\xad", '-').replace('•', '').split('\n')))))


def getTicketDataFromPageData(pageData):
    rawdata = getRawDataFromPageData(pageData)
    ticketType = getTicketTypeFromRawData(rawdata)
    print('ticketType', ticketType)
    if not ticketType:
        return None
    default_value = '-'
    data = dict(ticketType=ticketType, rawdata=rawdata)
    if ticketType == 1:

        data['traveller'] = rawdata[rawdata.index(
            'Traveler:')+1].upper() or default_value
        data['passport_no'] = default_value
        data['dob'] = default_value

        data['airline_name'] = rawdata[rawdata.index(
            'Airline')+6] or default_value
        data['status'] = rawdata[rawdata.index(
            'Status')+5].upper() or default_value
        data['flight_no'] = rawdata[rawdata.index(
            'Flight No')+5].split(' ').pop() or default_value
        data['cabin'] = rawdata[rawdata.index(
            'Cabin/Class')+5] or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[[i for i, x in enumerate(
            rawdata) if 'Airline PNR:' in x][0]].split(':')[1] or default_value
        data['ticket_no'] = default_value
        data['depart'] = rawdata[rawdata.index('Depart')+1] or default_value
        data['arrive'] = rawdata[rawdata.index('Arrive')+1] or default_value
        data['date'] = str(dateutil.parser.parse(" ".join(
            rawdata[rawdata.index('Date')+6].split(' ')[0:3])).date()) or default_value
        data['time'] = rawdata[rawdata.index('Time')+1] or default_value
        data['baggage'] = rawdata[rawdata.index('Baggage')+5] or default_value
        data['departure_terminal'] = default_value

        isReturnTrip = len(
            [i for i, x in enumerate(rawdata) if x == "Depart"]) > 1
        data['isReturnTrip'] = isReturnTrip

        if isReturnTrip:
            data['airline_name2'] = rawdata[[i for i, x in enumerate(
                rawdata) if x == "Airline"][1]+6] or default_value
            # data['status2'] = rawdata[[i for i, x in enumerate(rawdata) if x == "Status"][1]+5] or default_value
            data['flight_no2'] = rawdata[[i for i, x in enumerate(
                rawdata) if x == 'Flight No'][1]+5].split(' ').pop() or default_value
            data['cabin2'] = rawdata[[i for i, x in enumerate(
                rawdata) if x == 'Cabin/Class'][1]+5] or default_value
            data['stop2'] = default_value
            data['airline_pnr2'] = rawdata[[i for i, x in enumerate(
                rawdata) if 'Airline PNR:' in x][1]].split(':')[1] or default_value
            data['ticket_no2'] = default_value
            data['depart2'] = rawdata[[i for i, x in enumerate(
                rawdata) if x == "Depart"][1]+1] or default_value
            data['arrive2'] = rawdata[[i for i, x in enumerate(
                rawdata) if x == "Arrive"][1]+1] or default_value
            data['date2'] = str(dateutil.parser.parse(" ".join(rawdata[[i for i, x in enumerate(
                rawdata) if x == "Date"][3]+6].split(' ')[0:3])).date()) or default_value
            data['time2'] = rawdata[[i for i, x in enumerate(
                rawdata) if x == "Time"][2]+1] or default_value
            data['baggage2'] = rawdata[[i for i, x in enumerate(
                rawdata) if x == "Baggage"][1]+5] or default_value
            data['departure_terminal2'] = default_value
    elif ticketType == 2:
        traveller = rawdata[rawdata.index(
            'Passenger Name')+3].upper() or default_value
        data['traveller'] = traveller.split(
            '/')[1].split("-")[0].strip()+" " + traveller.split('/')[0].replace("_", " ")
        data['passport_no'] = rawdata[rawdata.index(
            'Passport No / National ID')+1] or default_value
        data['dob'] = default_value

        data['airline_name'] = rawdata[rawdata.index(
            'Flight Number')-5] or default_value
        data['status'] = default_value
        data['flight_no'] = data['airline_name'].split(' ')[0] or default_value
        data['cabin'] = rawdata[rawdata.index(
            'Class')+1].split(" ")[0] or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[rawdata.index(
            'Local PNR')+1] or default_value
        data['ticket_no'] = rawdata[rawdata.index(
            'Ticket number')+3] or default_value
        data['depart'] = rawdata[rawdata.index('Origin')-5] or default_value
        data['arrive'] = rawdata[rawdata.index(
            'Destination')-5] or default_value
        data['date'] = str(dateutil.parser.parse(" ".join(
            rawdata[rawdata.index('Flight Date')-5].split(" ")[1:])).date()) or default_value
        data['time'] = rawdata[rawdata.index('Flight time')-5] or default_value
        bdata = rawdata[rawdata.index('Checked Baggage')+5]
        if 'Bag' not in bdata:
            bdata = rawdata[rawdata.index('Checked Baggage')+8]
        else:
            if 'Bag' in rawdata[rawdata.index('Checked Baggage')+6]:
                bdata = rawdata[rawdata.index('Checked Baggage')+6]

        print(bdata)
        data['baggage'] = bdata.split(' ')[2]+' KG' or default_value

        data['departure_terminal'] = default_value

        isReturnTrip = len(
            [i for i, x in enumerate(rawdata) if x == "Origin"]) > 1
        data['isReturnTrip'] = isReturnTrip
    elif ticketType == 3:
        print(rawdata)
        data['traveller'] = " ".join(list(filter(lambda x: x.strip(
        ), rawdata[find_index_with_prefix(rawdata, 'Traveler:')].split(' ')))[1:]) or default_value
        data['passport_no'] = default_value
        data['dob'] = default_value

        data['airline_name'] = list(filter(lambda x: x.strip(), re.split(
            "  ", rawdata[rawdata.index('Airline')+11])))[0] or default_value
        data['status'] = default_value
        data['flight_no'] = list(filter(lambda x: x.strip(), re.split(
            "  ", rawdata[rawdata.index('Airline')+11])))[1] or default_value
        data['cabin'] = list(filter(lambda x: x.strip(), re.split(
            "  ", rawdata[rawdata.index('Airline')+11])))[2].split("/")[0].strip() or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[[i for i, x in enumerate(
            rawdata) if 'Airline PNR:' in x][0]].split(':')[1] or default_value
        data['ticket_no'] = rawdata[find_index_with_prefix(
            rawdata, 'E-Ticket Number:')].split(":")[1].strip() or default_value
        data['depart'] = rawdata[find_index_with_prefix(rawdata, 'Depart:')].split(
            ":")[1].split("(")[0].strip() or default_value
        data['arrive'] = rawdata[find_index_with_prefix(rawdata, 'Arrive:')].split(
            ":")[1].split("(")[0].strip() or default_value
        data['date'] = str(dateutil.parser.parse(rawdata[[i for i, x in enumerate(rawdata) if x.startswith(
            "Date:")][0]].split("Time:")[0].split(":")[1].strip()).date()) or default_value
        data['time'] = rawdata[[i for i, x in enumerate(
            rawdata) if x.startswith("Date:")][0]].split("Time:")
        if len(data['time']) > 1:
            data['time'] = data['time'][1].strip() or default_value
        else:
            data['time'] = rawdata[[i for i, x in enumerate(rawdata) if x.startswith(
                "Time:")][0]].split("Time:")[1].strip() or default_value
        data['baggage'] = "".join(list(filter(lambda x: x.strip(), re.split("  ", rawdata[rawdata.index(
            'Airline')+11])))[2].split("/")[1].split(" ")[3:]).strip() or default_value
        data['departure_terminal'] = rawdata[find_index_with_prefix(
            rawdata, "Departure Terminal:")].split(":")[1].strip() or default_value

        isReturnTrip = len([i for i, x in enumerate(
            rawdata) if x.startswith("Depart:")]) > 1
        data['isReturnTrip'] = isReturnTrip
    elif ticketType == 4:
        data['traveller'] = rawdata[rawdata.index(
            'Passenger\'s Name')+1].upper() or default_value
        data['passport_no'] = rawdata[rawdata.index(
            'Passport Number')+1].upper() or default_value
        data['dob'] = default_value

        data['airline_name'] = rawdata[rawdata.index(
            'Airline:')+1] or default_value
        data['status'] = default_value
        data['flight_no'] = rawdata[find_index_with_prefix(
            rawdata, 'Flight Number:')].split(":")[1] or default_value
        data['cabin'] = rawdata[rawdata.index(
            'Cabin Class:')+1] or default_value
        data['stop'] = default_value
        data['airline_pnr'] = rawdata[rawdata.index(
            'Airline reservation code (PNR):')+1] or default_value
        data['ticket_no'] = rawdata[rawdata.index(
            'Ticket Number:')+1] or default_value
        data['depart'] = rawdata[rawdata.index('Origin')+1] or default_value
        data['arrive'] = rawdata[rawdata.index(
            'Destination')+1] or default_value
        data['date'] = str(dateutil.parser.parse(
            rawdata[rawdata.index('Origin')+3]).date()) or default_value
        data['time'] = rawdata[rawdata.index(
            'Origin')+4].split(" ")[1] or default_value
        data['baggage'] = rawdata[rawdata.index(
            'Checked-in baggage')+1] or default_value
        data['departure_terminal'] = default_value
        data['isReturnTrip'] = False
    elif ticketType == 6:
        data['traveller'] = rawdata[rawdata.index(
            'Traveler:')+1] or default_value
        data['passport_no'] = default_value
        data['dob'] = default_value

        data['airline_name'] = rawdata[rawdata.index(
            'Airline')+5] or default_value
        data['status'] = default_value
        data['flight_no'] = rawdata[rawdata.index(
            'Flight No / Aircraft')+5].split("/")[0].strip() or default_value
        data['cabin'] = rawdata[rawdata.index(
            'Cabin / Stop')+4].split("/")[0].strip() or default_value
        data['stop'] = " ".join(rawdata[rawdata.index(
            'Cabin / Stop')+4].split("/")[1].split(" ")[0:3]).strip() or default_value
        data['airline_pnr'] = rawdata[[i for i, x in enumerate(
            rawdata) if 'Airline PNR:' in x][0]].split(':')[1] or default_value
        data['ticket_no'] = rawdata[find_index_with_prefix(
            rawdata, 'E-Ticket Number:')].split(":")[1].strip() or default_value
        data['depart'] = rawdata[find_index_with_prefix(rawdata, 'Depart:')].split(
            ":")[1].split("(")[0].strip() or default_value
        data['arrive'] = rawdata[find_index_with_prefix(rawdata, 'Arrive:')].split(
            ":")[1].split("(")[0].strip() or default_value
        data['date'] = str(dateutil.parser.parse(rawdata[[i for i, x in enumerate(rawdata) if x.startswith(
            "Date:")][0]].split("Time:")[0].split(":")[1].strip()).date()) or default_value

        data['time'] = rawdata[[i for i, x in enumerate(
            rawdata) if x.startswith("Date:")][0]].split("Time:")
        if len(data['time']) > 1:
            data['time'] = data['time'][1].strip() or default_value
        else:
            data['time'] = rawdata[[i for i, x in enumerate(rawdata) if x.startswith(
                "Time:")][0]].split("Time:")[1].strip() or default_value

        data['baggage'] = " ".join(rawdata[rawdata.index(
            'Cabin / Stop')+4].split("/")[1].split(" ")[3:]).strip() or default_value
        data['departure_terminal'] = rawdata[find_index_with_prefix(
            rawdata, "Departure Terminal:")].split(":")[1].strip() or default_value

        isReturnTrip = len([i for i, x in enumerate(
            rawdata) if x.startswith("Depart:")]) > 1
        data['isReturnTrip'] = isReturnTrip
    else:
        if ticketType == 5:
            datas = []
            i = rawdata.index('E TICKET DETAILS')+5
            for x in range(i, len(rawdata), 4):
                if rawdata[x] == 'FARE RULES':
                    break
                locdata = dict(ticketType=ticketType)
                locdata['traveller'] = rawdata[x]
                locdata['passport_no'] = default_value
                locdata['dob'] = default_value

                locdata['flight_no'] = rawdata[x+2]
                locdata['ticket_no'] = rawdata[x+3]
                locdata['airline_name'] = default_value
                locdata['airline_pnr'] = rawdata[rawdata.index(
                    'RESERVATION NUMBER (PNR)')+1] or default_value
                locdata['status'] = rawdata[rawdata.index(
                    'STATUS')+16] or default_value
                locdata['depart'] = rawdata[rawdata.index(
                    'ORIGIN /')+13] or default_value
                locdata['arrive'] = rawdata[rawdata.index(
                    'DESTINATION')+24] or default_value
                locdata['date'] = rawdata[rawdata.index(
                    'DEPARTURE /')+24] or default_value
                # check if last element is a n
                if not str(locdata['date'].split(" ")[-1]).strip().isnumeric():
                    if len(rawdata[rawdata.index('DEPARTURE /')+25].split(" ")) > 1:
                        locdata['date'] = f"{locdata['date']} {rawdata[rawdata.index('DEPARTURE /')+25].split(" ")[0]}".strip(
                        )
                        locdata['time'] = rawdata[rawdata.index(
                            'DEPARTURE /')+25].split(" ")[1].strip() or default_value
                    else:
                        locdata['date'] = f"{locdata['date']} {rawdata[rawdata.index('DEPARTURE /')+25]}".strip(
                        )
                        locdata['time'] = rawdata[rawdata.index(
                            'DEPARTURE /')+26].strip() or default_value
                else:
                    locdata['time'] = rawdata[rawdata.index(
                        'DEPARTURE /')+25] or default_value
                locdata['date'] = str(dateutil.parser.parse(
                    locdata['date']).date()) or default_value
                locdata['cabin'] = rawdata[rawdata.index(
                    'CLASS OF SERVICE')+15].split(" ")[0].strip() or default_value
                locdata['stop'] = default_value
                locdata['departure_terminal'] = default_value
                locdata['isReturnTrip'] = False
                locdata['baggage'] = default_value
                # find the index of Passport

                datas.append(locdata)

            passports = list(
                filter(lambda x: x.startswith('Passport No.'), rawdata))

            for locdata in datas:
                if len(passports) > 1:
                    travelername = None
                    for passp in passports:
                        travelername = rawdata[rawdata.index(
                            passp) - 1].strip()
                        if travelername == locdata['traveller']:
                            locdata['passport_no'] = passp.split(
                                "-")[1].strip()
                            locdata['dob'] = str(dateutil.parser.parse(
                                rawdata[rawdata.index(passp) + 1].split("-")[1].strip()).date())
                            break

                    if not travelername:
                        travelername = f"{rawdata[rawdata.index(passp) - 2]} {rawdata[rawdata.index(passp) - 1]}".strip(
                        )
                        if travelername == locdata['traveller']:
                            locdata['passport_no'] = passp.split(
                                "-")[1].strip()
                            locdata['dob'] = str(dateutil.parser.parse(
                                rawdata[rawdata.index(passp) + 1].split("-")[1].strip()).date())
                            break
            return datas
        else:
            return data
    return data


def create_output(inputfilename,
                  pagesData,
                  base_price,
                  airport_tax,
                  service_tax,
                  total_price,
                  logo=None,
                  dob=None,
                  passport=None,
                  traveler=None,
                  status=None,
                  flight_no=None,
                  depart=None,
                  arrive=None,
                  cabin=None,
                  stop=None,
                  date=None,
                  time=None,
                  airline_pnr=None,
                  ticket_no=None,
                  baggage=None,
                  departure_terminal=None,
                  isReturnTrip=False,
                  flight_no2=None,
                  cabin2=None,
                  stop2=None,
                  airline_pnr2=None,
                  ticket_no2=None,
                  depart2=None,
                  arrive2=None,
                  date2=None,
                  time2=None,
                  baggage2=None,
                  departure_terminal2=None,
                  ):
    skip_pages = []

    rd = getRawDataFromPageData(pagesData[0])
    ticketType = getTicketTypeFromRawData(rd)
    if ticketType == 5:
        newpagesdata = []
        for i in range(len(pagesData)):
            rd = getRawDataFromPageData(pagesData[i])
            if 'RESERVATION CONFIRMED' in rd:
                newpagesdata.append(pagesData[i])
                for j in range(i+1, len(pagesData)):
                    if 'RESERVATION CONFIRMED' not in getRawDataFromPageData(pagesData[j]):
                        newpagesdata[-1] += "\n" + pagesData[j]
        pagesData = newpagesdata

    for i in range(len(pagesData)):
        if i in skip_pages:
            continue
        ticket = getTicketDataFromPageData(pagesData[i])
        if not ticket:
            continue
        # print(ticket)
        # print(ticket)
        if ticketType == 4 and len(pagesData)-1 >= i+1:
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

        if ticketType != 5:
            tickets = [ticket]
        else:
            tickets = ticket

        for ti, ticket in enumerate(tickets):
            template = os.path.join(
                TEMPLATES_FOLDER, '2.pdf' if (isReturnTrip or ticket['isReturnTrip']) else '1.pdf')
            reader = PdfReader(template)
            writer = PdfWriter()
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            can.setFontSize(8)
            # check if airline logo exists

            can.drawString(20, 622, traveler or ticket['traveller'])
            can.drawString(260, 622, passport or ticket['passport_no'])
            can.drawString(360, 622, dob or ticket['dob'])
            can.drawString(445, 622, status or ticket['status'])

            if not logo:
                logo, _ = process.extractOne(
                    ticket['airline_name'], os.listdir(AIRLINES_FOLDER))
                can.drawString(60, 475, ticket['airline_name'])
            else:
                logo, _ = process.extractOne(logo, os.listdir(AIRLINES_FOLDER))
                can.drawString(60, 475, str(logo).split(".")
                               [0].replace("-", " ").title())
            if logo:
                can.drawImage(os.path.join(AIRLINES_FOLDER, logo),
                              6, 470, width=31, height=31)
            can.drawString(200, 475, flight_no or ticket['flight_no'])
            can.drawString(290, 475, cabin or ticket['cabin'])
            can.drawString(360, 475, stop or ticket['stop'])
            can.drawString(420, 475, airline_pnr or ticket['airline_pnr'])
            can.drawString(500, 475, ticket_no or ticket['ticket_no'])

            can.drawString(145, 460, depart or ticket['depart'])
            can.drawString(145, 445, arrive or ticket['arrive'])

            can.drawString(290, 445, date or ticket['date'])
            can.drawString(360, 445, time or ticket['time'])
            can.drawString(425, 445, baggage or ticket['baggage'])
            can.drawString(500, 445, departure_terminal or ticket['departure_terminal'])

            if not (isReturnTrip or ticket['isReturnTrip']):
                can.drawString(100, 382, base_price or "0.0")
                can.drawString(100, 367, airport_tax or "0.0")
                can.drawString(100, 352, service_tax or "0.0")
                can.drawString(100, 337, total_price)
            else:
                if not logo:
                    logo, _ = process.extractOne(
                        ticket['airline_name2'], os.listdir(AIRLINES_FOLDER))
                    can.drawString(60, 385, ticket['airline_name2'])
                else:
                    logo, _ = process.extractOne(
                        logo, os.listdir(AIRLINES_FOLDER))
                    can.drawString(60, 385, str(logo).split(".")
                                   [0].replace("-", " ").title())
                if logo:
                    can.drawImage(os.path.join(AIRLINES_FOLDER,
                                  logo), 6, 381, width=31, height=31)
                can.drawString(200, 385, flight_no2 or ticket.get('flight_no2','-'))
                can.drawString(290, 385, cabin2 or ticket.get('cabin2','-'))
                can.drawString(360, 385, stop2 or ticket.get('stop2','-'))
                can.drawString(420, 385, airline_pnr2 or ticket.get('airline_pnr2','-'))
                can.drawString(500, 385, ticket_no2 or ticket.get('ticket_no2','-'))
                can.drawString(145, 370, depart2 or ticket.get('depart2','-'))
                can.drawString(145, 355, arrive2 or ticket.get('arrive2','-'))
                can.drawString(290, 355, date2 or ticket.get('date2','-'))
                can.drawString(360, 355, time2 or ticket.get('time2','-'))
                can.drawString(425, 355, baggage2 or ticket.get('baggage2','-'))
                can.drawString(500, 355, departure_terminal2 or ticket.get('departure_terminal2','-'))

                can.drawString(95, 285, base_price or "0.0")
                can.drawString(95, 270, airport_tax or "0.0")
                can.drawString(95, 255, service_tax or "0.0")
                can.drawString(95, 240, total_price or "0.0")

            can.save()
            packet.seek(0)

            overlay_pdf = PdfReader(packet)
            page = reader.pages[0]
            page.merge_page(overlay_pdf.pages[0])
            writer.add_page(page)

            filename = f"new-{inputfilename}"
            if len(pagesData) > 1:
                filename = f"{filename}-p{i+1}"
            if len(tickets) > 1:
                filename = f"{filename}-t{ti+1}"
            filename = f"{filename}.pdf"
            with open(os.path.join(OUTPUT_FOLDER, filename), 'wb') as output_pdf:
                writer.write(output_pdf)


@app.post("/login/", response_class=HTMLResponse)
async def index(request: Request):
    body = await request.json()
    key = body.get('key', None)
    if not key:
        return JSONResponse(jsonable_encoder(dict(message=f"Invalid password.")), status_code=400)
    has = str(hash(str(key)))
    with open(hashfile, 'r',) as f:
        fr = f.read()
        if has != fr:
            return JSONResponse(jsonable_encoder(dict(message=f"Invalid password.")), status_code=400)
    return JSONResponse(jsonable_encoder(dict(key=has)), status_code=200)


def checkKey(key):
    if not key:
        return False
    with open(hashfile, 'r') as f:
        if key != f.read():
            return False
    return True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    key = request.query_params.get('key', None)
    if not checkKey(key):
        return templates.TemplateResponse("login.html", dict(request=request))

    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith(
        '.pdf') and os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    temps = [f for f in os.listdir(TEMPLATES_FOLDER) if f.lower().endswith(
        '.pdf') and os.path.isfile(os.path.join(TEMPLATES_FOLDER, f))]
    airlines = [f.capitalize() for f in os.listdir(AIRLINES_FOLDER) if f.lower().split(
        ".")[-1:][0] in ['png', 'jpg', 'jpeg'] and os.path.isfile(os.path.join(AIRLINES_FOLDER, f))]
    airlines.sort()
    outputs = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith(
        '.pdf') and f.lower().startswith('new-') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    # for each file, set the output file if name is new-{file}
    for file in files:
        if f"new-{file}" in outputs or len(list(filter(lambda x: x.startswith(f"new-{file.replace('.pdf', '')}"), outputs))):
            files[files.index(file)] = (file, f"new-{file}")
        else:
            files[files.index(file)] = (file, None)

    return templates.TemplateResponse("index.html", dict(request=request, key=key, files=files, templates=temps, airlines=airlines))


@app.get("/history/", response_class=HTMLResponse)
async def index(request: Request):
    key = request.query_params.get('key', None)
    if not checkKey(key):
        return templates.TemplateResponse("login.html", dict(request=request))

    outputs = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith(
        '.pdf') and f.lower().startswith('new-') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    return templates.TemplateResponse("output.html", dict(request=request, key=key, outputs=outputs))


@app.get("/airlines/", response_class=HTMLResponse)
async def index(request: Request):
    key = request.query_params.get('key', None)
    if not checkKey(key):
        return templates.TemplateResponse("login.html", dict(request=request))

    if not checkKey(request.query_params.get('key', None)):
        return templates.TemplateResponse("login.html", dict(request=request))

    airlines = [f.capitalize() for f in os.listdir(AIRLINES_FOLDER) if f.lower().split(
        ".")[-1:][0] in ['png', 'jpg', 'jpeg'] and os.path.isfile(os.path.join(AIRLINES_FOLDER, f))]
    airlines.sort()
    return templates.TemplateResponse("airlines.html", dict(request=request, key=key, airlines=airlines))


@app.post("/upload-airlines/", response_class=HTMLResponse)
async def upload_airlines(files: list[UploadFile] = File(...)):
    files = [file for file in files if file.content_type in [
        "image/png", "image/jpg", "image/jpeg"]]
    for file in files:
        if file.content_type in ["image/png", "image/jpg", "image/jpeg"]:
            file_path = os.path.join(
                AIRLINES_FOLDER, file.filename.lower().strip())
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        else:
            return JSONResponse(jsonable_encoder(dict(message=f"Invalid file type for {file.filename}. Only images are allowed.")), status_code=400)
    return RedirectResponse(url="/airlines", status_code=303)


@app.delete("/delete-airline/", response_class=HTMLResponse)
async def delete_airline(request: Request):
    file_name = request.query_params.get('file', None)

    if file_name:
        files = [file_name.lower()]
    else:
        return JSONResponse(jsonable_encoder(dict(message=f"Invalid file.")), status_code=400)
    for file in files:
        file_path = os.path.join(AIRLINES_FOLDER, file)
        if os.path.exists(file_path):
            os.remove(file_path)
    return RedirectResponse(url="/airlines", status_code=303)


@app.get("/airline-preview/", response_class=HTMLResponse)
async def airline_preview(request: Request):
    file_name = request.query_params.get('file', None)

    file_path = os.path.join(AIRLINES_FOLDER, file_name.lower())
    if not os.path.exists(file_path):
        return JSONResponse(jsonable_encoder(dict(message="Airline not found.")), status_code=404)

    return FileResponse(path=file_path, media_type=f'image/{file_name.split(".")[-1]}', filename=file_name)


@app.post("/upload-files/", response_class=HTMLResponse)
async def upload_files(files: list[UploadFile] = File(...)):
    """Handle multiple PDF file uploads."""
    for file in files:
        if file.content_type == "application/pdf":
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        else:
            return JSONResponse(jsonable_encoder(dict(message=f"Invalid file type for {file.filename}. Only PDFs are allowed.")), status_code=400)
    return RedirectResponse(url="/", status_code=303)


@app.get("/upload-preview/", response_class=HTMLResponse)
async def upload_preview(request: Request):
    file_name = request.query_params.get('file', None)
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        return JSONResponse(jsonable_encoder(dict(message="File not found.")), status_code=404)

    return FileResponse(path=file_path, media_type='application/pdf', filename=file_name)


@app.post("/upload-process/", response_class=HTMLResponse)
async def upload_process(request: Request):
    file_name = request.query_params.get('file', None)
    body = await request.json()
    if file_name:
        files = [dict(name=file_name,
                      base_price=body['base_price'],
                      airport_tax=body['airport_tax'],
                      service_tax=body['service_tax'],
                      total_price=body['total_price'],
                      airline=body['airline'],
                      passport=body['passport'],
                      dob=body['dob'],
                      traveler=body['traveler'],
                      status=body['status'],
                      flight_no=body['flight_no'],
                      depart=body['depart'],
                      arrive=body['arrive'],
                      cabin=body['cabin'],
                      stop=body['stop'],
                      date=body['date'],
                      time=body['time'],
                      airline_pnr=body['airline_pnr'],
                      ticket_no=body['ticket_no'],
                      baggage=body['baggage'],
                      departure_terminal=body['departure_terminal'],
                      isReturnTrip= body.get('isReturnTrip', False),
                      flight_no2=body.get('flight_no2', None),
                      cabin2=body.get('cabin2', None),
                      stop2=body.get('stop2', None),
                      airline_pnr2=body.get('airline_pnr2', None),
                      ticket_no2=body.get('ticket_no2', None),
                      depart2=body.get('depart2', None),
                      arrive2=body.get('arrive2', None),
                      date2=body.get('date2', None),
                      time2=body.get('time2', None),
                      baggage2=body.get('baggage2', None),
                      departure_terminal2=body.get('departure_terminal2', None),
                      )]
    else:
        files = body
    for file in files:
        pages = extract_pages_from_pdf(
            os.path.join(UPLOAD_FOLDER, file['name']))
        create_output(file['name'].replace('.pdf', ''), pages, file['base_price'], file['airport_tax'], file['service_tax'],
                      file['total_price'], file.get('airline', None), dob=file.get('dob', None), passport=file.get('passport', None),
                      traveler=file.get('traveler', None),
                      status=file.get('status', None),
                      flight_no=file.get('flight_no', None),
                      depart=file.get('depart', None),
                      arrive=file.get('arrive', None),
                      cabin=file.get('cabin', None),
                      stop=file.get('stop', None),
                      date=file.get('date', None),
                      time=file.get('time', None),
                      airline_pnr=file.get('airline_pnr', None),
                      ticket_no=file.get('ticket_no', None),
                      baggage=file.get('baggage', None),
                      departure_terminal=file.get('departure_terminal', None),
                      isReturnTrip= file.get('isReturnTrip', False),
                      flight_no2=file.get('flight_no2',None),
                      cabin2=file.get('cabin2',None),
                      stop2=file.get('stop2',None),
                      airline_pnr2=file.get('airline_pnr2',None),
                      ticket_no2=file.get('ticket_no2',None),
                      depart2=file.get('depart2',None),
                      arrive2=file.get('arrive2',None),
                      date2=file.get('date2',None),
                      time2=file.get('time2',None),
                      baggage2=file.get('baggage2',None),
                      departure_terminal2=file.get('departure_terminal2',None),
                      )

    return JSONResponse(jsonable_encoder(dict(message="Files processed.")))


@app.delete("/upload-clear/", response_class=HTMLResponse)
async def upload_clear(request: Request):

    file_name = request.query_params.get('file', None)

    if file_name:
        files = [file_name]
    else:
        files = [f for f in os.listdir(UPLOAD_FOLDER) if f.lower().endswith(
            '.pdf') and os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
    for file in files:
        file_path = os.path.join(UPLOAD_FOLDER, file)
        if os.path.exists(file_path):
            os.remove(file_path)
    return JSONResponse(jsonable_encoder(dict(message="Files cleared.")))


@app.get("/output-preview/", response_class=HTMLResponse)
async def output_preview(request: Request):
    file_name = request.query_params.get('file', None)
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
        files = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith(
            '.pdf') and f.startswith(f"{file_name.replace('.pdf', '')}")]
        if files:
            zip_file_path = f"{file_name}.zip"
            # create a separate folder and copy the files there
            for file in files:
                if not os.path.exists(os.path.join(OUTPUT_FOLDER, file_name.replace('.pdf', ''))):
                    os.mkdir(os.path.join(OUTPUT_FOLDER,
                             file_name.replace('.pdf', '')))
                shutil.copyfile(os.path.join(OUTPUT_FOLDER, file), os.path.join(OUTPUT_FOLDER, file_name.replace(
                    '.pdf', ''), file.replace(f"new-{file_name.replace('.pdf', '')}", '')))

            shutil.make_archive(file_name, "zip", os.path.join(
                OUTPUT_FOLDER, file_name.replace('.pdf', '')))

            shutil.rmtree(os.path.join(
                OUTPUT_FOLDER, file_name.replace('.pdf', '')))
            return FileResponse(
                f"{file_name}.zip",
                media_type="application/zip",
                filename=f"{file_name}.zip",
            )
        return JSONResponse(jsonable_encoder(dict(message="File not found.")), status_code=404)

    return FileResponse(path=file_path, media_type='application/pdf', filename=file_name)


@app.delete("/output-discard/", response_class=HTMLResponse)
async def output_discard(request: Request):
    file_name = request.query_params.get('file', None)
    if file_name:
        files = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith('.pdf') and f.startswith(
            file_name.replace('.pdf', '')) and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    else:
        files = [f for f in os.listdir(OUTPUT_FOLDER) if f.lower().endswith(
            '.pdf') and os.path.isfile(os.path.join(OUTPUT_FOLDER, f))]
    for file in files:
        file_path = os.path.join(OUTPUT_FOLDER, file)
        if os.path.exists(file_path):
            os.remove(file_path)
    return JSONResponse(jsonable_encoder(dict(message="Output cleared.")))
