# Download files from google drive and upload to S3

This repo contains a python tool to download files from a google drive folder, and to then upload the files to S3.

## Features

* Downloads the file to an in memory file handle and uploads from there without using precious disk space.
* Operates on one file at a time.
* Only speed limitation is network bandwith
* Downloads can be picked up from where you left off using the paging feature.
* Can take a file of known filenames and only upload files from google drive that match those.

## First time authentication

1. You will need to create a google drive app client for use with this script. You do this in your google API console.
1. You will need to download the client secret file and call it `client_secret.json`. place it in the same folder as the script.
1. On first run you'll be asked to authenticate the app and allow it full access to your drive (needs this in order to access files shared with you)

## Usage

This tool has built in help.

```(bash)
➜    python download-from-google-drive.py -h
usage: download-from-google-drive.py [-h] [--auth_host_name AUTH_HOST_NAME]
																		 [--noauth_local_webserver]
																		 [--auth_host_port [AUTH_HOST_PORT [AUTH_HOST_PORT ...]]]
																		 [--logging_level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
																		 --folder_id FOLDER_ID --bucket BUCKET
																		 --key-prefix KEY_PREFIX
																		 [--page-size PAGE_SIZE]
																		 [--start-page START_PAGE]
																		 [--end-page END_PAGE]
																		 [--match-file MATCH_FILE]

optional arguments:
	-h, --help            show this help message and exit
	--auth_host_name AUTH_HOST_NAME
												Hostname when running a local web server.
	--noauth_local_webserver
												Do not run a local web server.
	--auth_host_port [AUTH_HOST_PORT [AUTH_HOST_PORT ...]]
												Port web server should listen on.
	--logging_level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
												Set the logging level of detail.
	--folder_id FOLDER_ID, -f FOLDER_ID
												Google Drive Folder ID (it's the end of the folder URI!)
	--bucket BUCKET, -b BUCKET
												Name of S3 bucket to use
	--key-prefix KEY_PREFIX, -k KEY_PREFIX
												Key prefix to use (path to a folder)
	--page-size PAGE_SIZE, -p PAGE_SIZE
												Number of files in each page
	--start-page START_PAGE, -s START_PAGE
												start from page N of the file listing
	--end-page END_PAGE, -e END_PAGE
												stop paging at page N of the file listing
	--match-file MATCH_FILE
												Only process files if the filename is in this file
```

A typical command to download all files and upload to S3 would be:

```(bash)
python download-from-google-drive.py -f idofthegooglefolder -b my-bucket -k path/to/files/in/bucket
```

A typical command to download only files which match a supplied checklist of files and upload to S3:

The checklist file contains a filename one per line.

```(bash)
python download-from-google-drive.py -f idofthegooglefolder -b my-bucket -k path/to/files/in/bucket --match-file checklist_file.txt
```

You may need to process thousands of files but only want to work on them in distinct batches so that you can pick up where you left off.

The script defaults to 100 files per page, but this can be adjusted. This example processes a list of files in a google drive folder paging 10 at a time, starting at page 20 and ending at page 30.

```(bash)
python download-from-google-drive.py -f idofthegooglefolder -b my-bucket -k path/to/files/in/bucket -s 20 -e 30 -p 10
```

## Todos

* [ ] Allow the S3 and Google drive steps to be decoupled. I.e. just download to a local directory
* [ ] Allow traversal of multiple directories.
* [ ] Preserve directory structure in S3
