# Implementing Calendar Relay

## Google Calendar Interop
Google has a function called Calendar Interop that can be used to allow Google to make calendar lookup requests when invitees are added to calendar events.  

Google has documentation here: https://support.google.com/a/answer/7444958 

However, that functionality uses old APIs and credential requirements that are not accepted by some organizations.  

To solve the issues above, an application has been created that can translate Google’s requests into something that can connect to Office365 with lowered permissions.  That application is called Calendar Relay and is currently implemented as a Python/Flask application that runs as a web service.  The source code is available in this open source project, but needs to be hosted and configured in a web server.

### Configuring Google Calendar Interop
Note: The configuration of this tool requires the Calendar Relay server to be available.

Google provides a tool that can be used to configure how they will look up external calendars called Calendar Interop management.  It can be found in your Google Admin settings here: 
https://admin.google.com/ac/apps/calendar/settings/interop

#### You will need to fill in the information as below:

* Enable Interoperability for Calendar: Enabled
* Type: Exchange Web Services (EWS)
* Exchange Web Services URL: your Calendar Relay server (https://calendar-relay.your-server.com/)
* Exchange Role Account: a fake email address whose domain is the one you want to look up calendars for (test@example.com)
* Authentication type: OAuth 2.0
* Token endpoint URL: your Calendar Relay server’s token endpoint (https://calendar-relay.your-server.com/token)
* Application (client) ID: (See Calendar Relay/Credentials/Google authentication below)
* Client secret: (See Calendar Relay/Credentials/Google authentication below)

#### You should also add Additional Exchange endpoints:

The source code currently supports relaying requests to one Office365 tenant.  However, it does support multiple email domains within that tenant.

Create an entry each for each domain whose calendars you are integrating against.
For each, the URLs and client id/secrets are the same.
The Supported domains and Exchange Role account should be changed for each domain.
*Note: We suggest separating each domain in case there are permissions issues with users seeing across domains.*

## Calendar Relay

The team implementing the server will need to determine the best method for storing the credentials this service uses.  Although the source code has locations to place them in the code, these should be replaced with a real secrets management solution.

You must have SSL enabled (with a valid certificate) for Google to connect to the service correctly.

There are multiple endpoint URLs defined for the code:
/ - Where the calendar lookups are performed
/token - Where the Google credentials are verified
/health-check - (optional) Used for system monitoring

### Credentials

#### MS Graph API
You will need the Exchange Administrator to generate API credentials that will be used to look up the calendar free/busy information.

A set of client id and secret that have the following permissions:
* MS Graph API
	* Delegated: User.Directory
	* Application: Calendar.read

You will also need the Tenant ID for these credentials.

Add these credentials to your Secrets Management system (or directly into the source code)
* The API Client ID is referenced as 'graph_client_id'
* The API Client Secret is referenced as 'graph_client_secret'
* The Tenant ID should be combined with "https://login.microsoftonline.com/" to become the 'graph_authority'

#### Google authentication

You will need to generate a client id/secret pair to put in the Google Calendar Interop Management tool, that will be used by Google to authenticate against your Calendar Relay service.

Add these credentials to your Secrets Management system (or directly into the source code), as well as in the Google Interop Management tool.
The Client ID is referenced as 'google_client_id'
The Client Secret is referenced as 'google_client_secret'

### IP Access and HTTPS

From https://support.google.com/a/answer/7437483?hl=en:

On port 443, turn on inbound internet connectivity so Google Calendar can reach the server. This step requires a valid SSL certificate *issued by a trusted public internet root Certificate Authority*.

If you’re blocking external incoming network traffic, add the following address ranges to your allowlist to permit requests originating from Calendar Interop.

If you use IPv4, add the following IP range to your allowlist: 
* 74.125.88.0/27.

If you use IPv6, add the following IP blocks to your allowlist:

* 2001:4860:4::/64
* 2404:6800:4::/64
* 2607:f8b0:4::/64
* 2800:3f0:4::/64
* 2a00:1450:4::/64
* 2c0f:fb50:4::/64
