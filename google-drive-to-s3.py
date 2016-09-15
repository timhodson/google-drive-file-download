from __future__ import print_function
from googleapiclient.http import MediaIoBaseDownload
import httplib2
import os
import sys
import datetime
import time

from apiclient import discovery
import io
import oauth2client
from oauth2client import client
from oauth2client import tools

from logbook import Logger, FileHandler, StreamHandler
from progress_bar import InitBar

import boto3

log = Logger('google-drive-to-s3')

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser])
    # add in our specific command line requirements
    flags.add_argument('--folder_id', '-f', type=str, required=True,
                       help="Google Drive Folder ID (it's the end of the folder URI!) (required)")
    flags.add_argument('--bucket', '-b', type=str, required=True,
                       help="Name of S3 bucket to use (required)")
    flags.add_argument('--key-prefix', '-k', type=str, required=True,
                       help="Key prefix to use as the path to a folder in S3 (required)")
    flags.add_argument('--page-size', '-p', type=int, default=100,
                       help="Number of files in each page (defaults to 100)")
    flags.add_argument('--start-page', '-s', type=int, default=1,
                       help="start from page N of the file listing (defaults to 1)")
    flags.add_argument('--end-page', '-e', type=int, default=None,
                       help="stop paging at page N of the file listing (defaults to not stop before the end)")
    flags.add_argument('--match-file', type=str, default=None,
                       help="Only process files if the filename is in this file (defaults to process all files)")
    flags.add_argument('--log-dir', '-l', type=str, help='Where to put log files', default='/tmp')
    flags.add_argument('--log-level', type=str, help='Choose a log level', default='INFO')
    args = flags.parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/drive-python-quickstart.json
# SCOPES = 'https://www.googleapis.com/auth/drive.metadata.readonly'
SCOPES = 'https://www.googleapis.com/auth/drive'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Transfer from Google Drive to S3'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'download-from-google-drive-to-s3.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, args)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials


def ensure_trailing_slash(val):
    if val[-1] != '/':
        return "{}/".format(val)
    return val


def we_should_process_this_file(filename, match_files):
    if not match_files:  # We have not supplied any file names to match against, so process everything.
        return True
    if filename in match_files:
        return True
    return False


def main():
    """Shows basic usage of the Google Drive API.

    Creates a Google Drive API service object and outputs the names and IDs
    for up to 10 files.
    """

    log_filename = os.path.join(
        args.log_dir,
        'google-drive-to-s3-{}.log'.format(os.path.basename(time.strftime('%Y%m%d-%H%M%S')))
    )

    # register some logging handlers
    log_handler = FileHandler(
        log_filename,
        mode='w',
        level=args.log_level,
        bubble=True
    )
    stdout_handler = StreamHandler(sys.stdout, level=args.log_level, bubble=True)

    with stdout_handler.applicationbound():
        with log_handler.applicationbound():
            log.info("Arguments: {}".format(args))
            start = time.time()
            log.info("starting at {}".format(time.strftime('%l:%M%p %Z on %b %d, %Y')))

            credentials = get_credentials()
            http = credentials.authorize(httplib2.Http())
            drive_service = discovery.build('drive', 'v3', http=http)

            s3 = boto3.resource('s3')

            # load up a match file if we have one.
            if args.match_file:
                with open(args.match_file, 'r') as f:
                    match_filenames = f.read().splitlines()
            else:
                match_filenames = None

            # get the files in the specified folder.
            files = drive_service.files()
            request = files.list(
                pageSize=args.page_size,
                q="'{}' in parents".format(args.folder_id),
                fields="nextPageToken, files(id, name)"
            )

            # make sure our S3 Key prefix has a trailing slash
            key_prefix = ensure_trailing_slash(args.key_prefix)

            page_counter = 0
            file_counter = 0
            while request is not None:
                file_page = request.execute(http=http)
                page_counter += 1
                page_file_counter = 0  # reset the paging file counter

                # determine the page at which to start processing.
                if page_counter >= args.start_page:
                    log.info(u"######## Page {} ########".format(page_counter))

                    for this_file in file_page['files']:
                        file_counter += 1
                        page_file_counter += 1
                        if we_should_process_this_file(this_file['name'], match_filenames):
                            log.info(u"#== Processing {} file number {} on page {}. {} files processed.".format(
                                this_file['name'],
                                page_file_counter,
                                page_counter,
                                file_counter
                            ))

                            # download the file
                            download_request = drive_service.files().get_media(fileId=this_file['id'])
                            fh = io.BytesIO()  # Using an in memory stream location
                            downloader = MediaIoBaseDownload(fh, download_request)
                            done = False
                            pbar = InitBar(this_file['name'])
                            while done is False:
                                status, done = downloader.next_chunk()
                                pbar(int(status.progress()*100))
                                # print("\rDownload {}%".format(int(status.progress() * 100)))
                            del pbar

                            # upload to bucket
                            log.info(u"Uploading to S3")
                            s3.Bucket(args.bucket).put_object(
                                Key="{}{}".format(key_prefix, this_file['name']),
                                Body=fh.getvalue(),
                                ACL='public-read'
                            )
                            log.info(u"Uploaded to S3")
                            fh.close()  # close the file handle to release memory
                        else:
                            log.info(u"Do not need to process {}".format(this_file['name']))

                # stop if we have come to the last user specified page
                if args.end_page and page_counter == args.end_page:
                    log.info(u"Finished paging at page {}".format(page_counter))
                    break
                # request the next page of files
                request = files.list_next(request, file_page)

            log.info("Running time: {}".format(str(datetime.timedelta(seconds=(round(time.time() - start, 3))))))
            log.info("Log written to {}:".format(log_filename))


if __name__ == '__main__':
    main()
