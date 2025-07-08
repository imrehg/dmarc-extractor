import datetime
import gzip
import ipaddress
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import click
import geoip2.database
import geoip2.webservice
import requests
from dataclasses_json import config
from defusedxml.ElementTree import parse as xml_parse
from dynaconf import Dynaconf

from jmapc import Client, EmailQueryFilterCondition, MailboxQueryFilterCondition, Ref
from jmapc.logging import log
from jmapc.methods import (
    CustomMethod,
    EmailGet,
    EmailQuery,
    IdentityGet,
    IdentityGetResponse,
    MailboxGet,
    MailboxGetResponse,
    MailboxQuery,
)
from jmapc.methods.base import Get, GetResponse

# Create basic console logger
logging.basicConfig()

# Set jmapc log level to DEBUG
log.setLevel(logging.DEBUG)


settings = Dynaconf(
    envvar_prefix="MYPROGRAM",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
    env_switcher="MYPROGRAM_ENV",
)


def get_identity(client: Client) -> None:
    # Create and configure client

    # Prepare Identity/get request
    # To retrieve all of the user's identities, no arguments are required.
    method = IdentityGet()

    # Call JMAP API with the prepared request
    result = client.request(method)

    # Print some information about each retrieved identity
    assert isinstance(
        result, IdentityGetResponse
    ), "Error in Identity/get method"  # nosec B101 # TODO: Replace with proper exception handling
    for identity in result.data:
        print(f"Identity {identity.id} is for " f"{identity.name} at {identity.email}")

    # Example output:
    #
    # Identity 12345 is for Ness at ness@onett.example.com
    # Identity 67890 is for Ness at ness-alternate@onett.example.com


def dmarcprint(root):

    rpt_md = root.find("report_metadata")

    org_name = rpt_md.find("org_name").text
    begtime = datetime.datetime.fromtimestamp(
        int(rpt_md.find("date_range").find("begin").text)
    )
    endtime = datetime.datetime.fromtimestamp(
        int(rpt_md.find("date_range").find("end").text)
    )

    print(
        "Report from " + org_name + " for " + str(begtime) + " to " + str(endtime) + ":"
    )

    for record in root.findall("record"):
        restext = record.find("row").find("policy_evaluated").find("disposition").text
        if restext == "none":
            restext = "Pass"
        spftext = (
            " SPF: " + record.find("row").find("policy_evaluated").find("spf").text
        )
        dkimtext = (
            " DKIM: " + record.find("row").find("policy_evaluated").find("dkim").text
        )
        for sres in record.find("auth_results").findall("spf"):
            spftext += (
                " Domain: "
                + sres.find("domain").text
                + " "
                + sres.find("result").text
                + "ed."
            )
        for dres in record.find("auth_results").findall("dkim"):
            dkimtext += (
                " Domain: "
                + dres.find("domain").text
                + " "
                + dres.find("result").text
                + "ed."
            )

        print(
            record.find("row").find("count").text
            + " from "
            + record.find("row").find("source_ip").text
            + ": "
            + restext
        )
        print(spftext)
        print(dkimtext)
        print("")


def mailbox_query(client: Client) -> None:
    # EmailBodyPart(part_id='2', blob_id='G3839cbb8f679f9f2e619696455b909e573c1d6c2', size=429, headers=None, name='yahoo.com!imreh.net!1751241600!1751327999.xml.gz', type='application/gzip', charset=None, disposition='attachment', cid=None, language=None, location=None, sub_parts=None)
    print(client.jmap_session)

    blob_id = "G3839cbb8f679f9f2e619696455b909e573c1d6c2"
    account_id = "u4be94060"

    blob_data = {
        "accountId": account_id,
        "ids": [
            blob_id,
        ],
        "properties": ["data:asText", "digest:sha", "size"],
    }

    methods = [
        MailboxQuery(filter=MailboxQueryFilterCondition(name="DMARC")),
        MailboxGet(ids=Ref("/ids")),
        EmailQuery(
            filter=EmailQueryFilterCondition(
                to="dmarc@imreh.net",
                after=datetime.datetime.now() - datetime.timedelta(days=5),
                has_attachment=True,
            ),
        ),
        EmailGet(
            ids=Ref("/ids"),
            properties=["blobId", "messageId", "attachments", "bodyValues"],
            fetch_all_body_values=True,
        ),
        # BlobGet(ids=[blob_id])
    ]

    # Call JMAP API with the prepared request
    results = client.request(methods)
    print(">" * 10)

    print(results[2])
    print(results[3])

    account_id = results[3].response.account_id
    jmap_base_url = settings.jmap_host
    print("+" * 10)
    for mail in results[3].response.data:

        # print(mail)
        # print("-" * 10)
        # continue
        for attachment in mail.attachments:
            print(attachment)
            blob_id = attachment.blob_id
            file_name = attachment.name
            local_path = Path("attachments") / file_name
            # attachment.
            print(blob_id)
            with tempfile.NamedTemporaryFile() as f:
                client.download_attachment(attachment, f.name)
                if attachment.type == "application/gzip":
                    with gzip.open(f.name, "rb") as a:
                        # file_content = a.read()
                        et = xml_parse(a)
                        # print(et)
                        dmarcprint(et)

    # https://beta.fastmailusercontent.com/jmap/download/u4be94060/G59ddf84c242974cdf6e4819b1bcd0501aa89dce1/google.com!imreh.net!1749772800!1749859199.zip?type=application%2Fzip&u=4be94060&access_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIwMWY3ZDhhZWZkMjNjNTUxNjAyNmQ3MTM2NDY3MjAyNyIsInN1YiI6IkYzdm16MkxzVVRHd0dBVHJXTF9fcVhEV3Y1WW8yVHY1NG9hRXJqSTg1ckkiLCJpYXQiOjE3NTE2OTUyMDB9.4dVKFvsGsogPd6jgXo6AX2n6kLNLCCebpgXkY1ce2H4&download=1

    # local_filename = file_name
    # headers = {"Authentication": f"Bearer {settings.jmap_api_token}"}
    # query_params = {
    #     "u": account_id,
    #     "type": attachment.type,
    #     "download": 1,
    #     "access_token": settings.jmap_api_token,
    # }
    # r = requests.get(attachment_url, headers=headers, stream=True, params=query_params)
    # with open(local_filename, 'wb') as f:
    #     for chunk in r.iter_content(chunk_size=1024):
    #         if chunk: # filter out keep-alive new chunks
    #             f.write(chunk)
    #             # f.flush() commented by recommendation from J.F.Sebastian
    return
    # Retrieve the InvocationResponse for the second method. The InvocationResponse
    # contains the client-provided method ID, and the result data model.
    method_2_result = results[1]

    # Retrieve the result data model from the InvocationResponse instance
    method_2_result_data = method_2_result.response

    # Retrieve the Mailbox data from the result data model
    assert isinstance(
        method_2_result_data, MailboxGetResponse
    ), "Error in Mailbox/get method"  # nosec B101 # TODO: Replace with proper exception handling
    mailboxes = method_2_result_data.data

    # Although multiple mailboxes may be present in the results, we only expect a
    # single match for our query. Retrieve the first Mailbox from the list.
    mailbox = mailboxes[0]

    # Print some information about the mailbox
    print(f"Found the mailbox named {mailbox.name} with ID {mailbox.id}")
    print(
        f"This mailbox has {mailbox.total_emails} emails, "
        f"{mailbox.unread_emails} of which are unread"
    )


def main():
    print("Hello from dmarc-extractor!")
    mail_client = Client.create_with_api_token(
        host=settings.jmap_host, api_token=settings.jmap_api_token
    )
    # get_identity(mail_client)
    mailbox_query(mail_client)


def ip_lookup(ip: Union[str, ipaddress.IPv4Address, ipaddress.IPv6Address]):
    """WIP checks for IP addresses from local GeoLite2 databases"""
    with (
        geoip2.database.Reader("/var/lib/GeoIP/GeoLite2-City.mmdb") as city_reader,
        geoip2.database.Reader("/var/lib/GeoIP/GeoLite2-ASN.mmdb") as asn_reader,
    ):
        response = city_reader.city(ip)
        print(response.country.iso_code)
        print(response.country.name)
        print(response.continent.name)
        if len(response.subdivisions) > 0:
            print(response.subdivisions[0].name)
        print(response.city.name)
        print(response.location.latitude, response.location.longitude)
        print(response.postal.code)

        asn_response = asn_reader.asn(ip)
        print(asn_response.autonomous_system_number)
        print(asn_response.autonomous_system_organization)


@click.command()
@click.option(
    "-a",
    "--all",
    type=bool,
    default=False,
    help="Whether to process all attachments. Useful to re-process data in case the extractor code changed.",
)
def cli() -> None:
    """DMARC record extractor CLI"""
    print("yey!")


if __name__ == "__main__":
    main()
