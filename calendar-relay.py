from pprint import pprint
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace
import logging
import json
import requests

from flask import Flask, request
import msal
import xmltodict

SCOPE = ["https://graph.microsoft.com/.default"]

app = Flask(__name__)


"""
You will want to replace the credentials below with your 
own data or calls to a secrets manager.
"""

# used to validate the credentials sent by Google
app.config['google_client_id'] = ""

# used to validate the credentials sent by Google
app.config['google_client_secret'] = ""

# used to authenticate against the MS Graph api
app.config['graph_client_id'] = ""

# used to authenticate against the MS Graph api
app.config['graph_client_secret'] = ""

# This is the MS Graph API endpoint.  
# For Office365 it would look like this: 
# "https://login.microsoftonline.com/<the tenant id>"
app.config['graph_authority'] = ""

@app.route("/health-check")
def health_check():
    return "success"

@app.route("/token", methods=['GET', 'POST'])
def authenticate():
    """
    This function compares the credenials being sent by Google to our expected 
    values.
    NOTE: This is impersonating an OAuth flow, not actually giving back a real 
    OAuth access token
    """
    args = request.form
    expected_client_id = app.config['google_client_id']
    expected_client_secret = app.config['google_client_secret']
    # Verify credentials in the request
    if expected_client_id != args.get('client_id') or \
            expected_client_secret != args.get('client_secret'):
        logging.info("Wrong oauth credentials.")
        return dict()
    return dict(access_token="some_access_token")  #this is a fake token


@app.route("/", methods=['GET', 'POST'])
def get_schedule():
    """
    This is the main function for getting the request from Google, talking to 
    the MS Graph API and then returning the data to Google.
    """
    accounts, timing = parse_google_request(request)
    msgraph_response = send_to_msgraph(accounts, timing)
    xml_payload = build_xml_response(msgraph_response)
    return xml_payload

def parse_google_request(request):
    """
    This function takes the data from the EWS API call from Google, reformats 
    it for MS Graph API.

    Arguments:
        request (request): the payload from Google hitting the endpoint
    Returns: 
        accounts (an orderedDict if one, or a list if multiple accounts):
            the email address(es) whose calendars we want to look up
        timing (dict): information about the time period we want the
            calendar availability for.
    """
    # Parse google's get schedule XML request
    tree = xmltodict.parse(request.data)
    header = tree['SOAP-ENV:Envelope']['SOAP-ENV:Header']
    body = tree['SOAP-ENV:Envelope']['SOAP-ENV:Body']['ns3:GetUserAvailabilityRequest']
    # example: "dateTime": "2020-10-12T18:00:00",
    timing = {}
    timing['start_time'] = body['ns2:FreeBusyViewOptions']['ns2:TimeWindow']['ns2:StartTime']
    timing['end_time'] = body['ns2:FreeBusyViewOptions']['ns2:TimeWindow']['ns2:EndTime']
    timing['availability_view_interval'] = body['ns2:FreeBusyViewOptions']['ns2:MergedFreeBusyIntervalInMinutes']
    accounts = []
    mailboxes = body['ns3:MailboxDataArray']['ns2:MailboxData']
    # one mailbox is an orderedDict, multiple mailboxes are in a list
    if isinstance(mailboxes, list):
        for mailbox in mailboxes:
            accounts.append(mailbox['ns2:Email']['ns2:Address'])
    else:
        accounts = [mailboxes['ns2:Email']['ns2:Address']]
    return accounts, timing

def send_to_msgraph(accounts, timing):
    """
    Take the list of accounts and timing info and request the schedule from 
    MS Graph API

    Arguments:
        accounts (an orderedDict if one, or a list if multiple accounts):
            the email address(es) whose calendars we want to look up
        timing (dict): information about the time period we want the
            calendar availability for.
    Returns:
        graph_data (dict): contains schedule info as returned by MS Graph API
    """
    # Use Graph API to get calendar schedule
    msal_app = msal.ConfidentialClientApplication(app.config['graph_client_id'],
                                                  authority=app.config['graph_authority'],
                                                  client_credential=app.config['graph_client_secret'])
    result = msal_app.acquire_token_silent(SCOPE, account=None)
    if not result:
        logging.info("No suitable token exists in cache. Let's get a new one from AAD.")
        result = msal_app.acquire_token_for_client(scopes=SCOPE)

    if "access_token" in result:
        data = dict(Schedules=accounts,
                    StartTime=dict(dateTime=timing['start_time'], timeZone="Pacific Standard Time"),
                    EndTime=dict(dateTime=timing['end_time'], timeZone="Pacific Standard Time"),
                    availabilityViewInterval=timing['availability_view_interval'])

        graph_data = requests.post(
            url=f'https://graph.microsoft.com/v1.0/users/{accounts[0]}/calendar/getSchedule',
            headers={'Authorization': 'Bearer ' + result['access_token'],
                     'Content-Type': 'application/json'},
            data=json.dumps(data)).json()
    else:
        print(result.get("error"))
        print(result.get("error_description"))
    return graph_data


def build_xml_response(graph_data):
    """
    Convert graph API get_schedule() response to xml format that google accepts

    Arguments:
        graph_data (dict): contains schedule info as returned by MS Graph API
    Returns:
        (str): returns a string formatted as a response to an EWS Calendar lookup.
    """
    register_namespace('s', 'http://schemas.xmlsoap.org/soap/envelope/')
    Envelope = Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope')
    Body = SubElement(Envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    GetUserAvailabilityResponse = SubElement(
        Body,
        'GetUserAvailabilityResponse',
        {'xmlns': 'http://schemas.microsoft.com/exchange/services/2006/messages',
         'xmlns:xsd': 'http://www.w3.org/2001/XMLSchema',
         'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance'})
    FreeBusyResponseArray = SubElement(GetUserAvailabilityResponse, 'FreeBusyResponseArray')

    for schedule in graph_data.get('value'):
        FreeBusyResponse = SubElement(FreeBusyResponseArray, 'FreeBusyResponse')
        ResponseMessage = SubElement(FreeBusyResponse, 'ResponseMessage')
        ResponseMessage.set('ResponseClass', 'Success')
        ResponseCode = SubElement(ResponseMessage, 'ResponseCode')
        ResponseCode.text = 'NoError'
        FreeBusyView = SubElement(FreeBusyResponse, 'FreeBusyView')
        FreeBusyViewType = SubElement(
            FreeBusyView,
            'FreeBusyViewType',
            {'xmlns': 'http://schemas.microsoft.com/exchange/services/2006/types'})
        FreeBusyViewType.text = 'FreeBusyMerged'
        CalendarEventArray = SubElement(
            FreeBusyView,
            'CalendarEventArray',
            {'xmlns': 'http://schemas.microsoft.com/exchange/services/2006/types'})

        schedules = schedule.get('scheduleItems')
        for s in schedules:
            # skip free events
            if s.get('status') == 'free':
                continue
            # 2020-10-05T21:00:00 timezone UTC
            s_time = s.get('start').get('dateTime')[:19]
            e_time = s.get('end').get('dateTime')[:19]

            CalendarEvent = SubElement(CalendarEventArray, 'CalendarEvent')
            StartTime = SubElement(CalendarEvent, 'StartTime')
            EndTime = SubElement(CalendarEvent, 'EndTime')
            BusyType = SubElement(CalendarEvent, 'BusyType')
            StartTime.text = s_time
            EndTime.text = e_time
            BusyType.text = 'Busy'
    return tostring(Envelope, encoding='utf8', method='xml')
