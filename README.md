#  DMARC reports exporter

This project is to facilitate exporting and collecting DMARC reports, so for example you can analyse the results yourself.

The current codebase is quite specific to my use case, the purpose being a a good learning experience besides a practical project as well.

Ther workflow of the tool is as follows:

- Pull DMARC message attachments from a JMAP server
- Extract the useful fields from the XML report
- Look up IP information
- Combine all these data and push to a Google Sheet

## Pre-requisits

DMARC DNS record configuration for your domain.

Have a JMAP-enabled mail server (such as [Fastmail](https://fastmail.com)), where a folder/label receives all the DMARC reports for the domains that you'd like to analyse. Ideally you've already received some messages with reports.

GeoLite2 dataset access for IP resolution (API keys from [Maxmind](https://www.maxmind.com)).

## Installation

## Configuration

## Setting up Systemd timers for scheduled runs

## FAQ
