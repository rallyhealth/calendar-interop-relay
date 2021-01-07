# Calendar-Interop-Relay

A simple python-flask webservice that can take requests from the Google Calendar Interop system, deconstruct the request, reformat the request and send it to an MS Graph API endpoint with separate credentials.  It can then take the response, deconstruct and reformat it back to the XML that Google wants and send it back.

This solves a few issues:

1. Google stores the credentials used for their Calendar Interop system seemingly in plain text (our system uses separate credentials for the MS leg that can be stored securely by the implementor)
2. The legacy EWS API that Google currently uses, requires API credentials with full Exchange admin access.  That is unacceptable for many organizations.  The MS Graph API requires minimally permissioned credentials.

You will need to provide your own credentials source.  We have stubbed out how to do it with hardcoded credentials, but it is not recommended.

See implementation.md for more information.