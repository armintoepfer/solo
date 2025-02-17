import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

def get_xml_text(element, path, namespaces=None):
    """Helper function to safely get text from an XML element."""
    try:
        if namespaces:
            found = element.find(path, namespaces)
        else:
            found = element.find(path)
        return found.text if found is not None else None
    except Exception as e:
        logger.error(f"Error getting XML text: {str(e)}")
        return None

def parse_soap_response(response_text, xpath, namespaces=None):
    """Helper function to parse SOAP responses."""
    try:
        root = ET.fromstring(response_text)
        if namespaces:
            element = root.find(xpath, namespaces)
        else:
            # Try with wildcard namespace if no specific namespaces provided
            element = root.find(xpath.replace('u:', '{*}'))
            if element is None:
                # Try without namespace
                element = root.find(xpath.split('/')[-1])
        return element.text if element is not None else None
    except ET.ParseError as e:
        logger.error(f"Error parsing SOAP response: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing SOAP response: {str(e)}")
        return None

def create_soap_body(service, action, **kwargs):
    """Helper function to create SOAP request bodies."""
    body = f"""<?xml version="1.0"?>
    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
        <s:Body>
            <u:{action} xmlns:u="urn:schemas-upnp-org:service:{service}">"""

    for key, value in kwargs.items():
        body += f"\n                <{key}>{value}</{key}>"

    body += f"""
            </u:{action}>
        </s:Body>
    </s:Envelope>"""

    return body

def create_soap_headers(service, action):
    """Helper function to create SOAP headers."""
    return {
        'Content-Type': 'text/xml; charset="utf-8"',
        'SOAPACTION': f'"urn:schemas-upnp-org:service:{service}#{action}"'
    }
