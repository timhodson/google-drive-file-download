from __future__ import print_function
import datetime
import time
import httplib2
import os
import sys

from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

from logbook import Logger, FileHandler, StreamHandler

log = Logger('copy-google-drive-folder')

try:
    import argparse

    flags = argparse.ArgumentParser(parents=[tools.argparser])
    # add in our specific command line requirements
    flags.add_argument('--source-folder_id', '-f', type=str, required=True,
                       help="Source Google Drive Folder ID (it's the end of the folder URI!) (required)")
    flags.add_argument('--target-folder_id', '-t', type=str, required=True,
                       help="Target Google Drive Folder ID (it's the end of the folder URI!) (required)")
    flags.add_argument('--page-size', '-p', type=int, default=100,
                       help="Number of files in each page (defaults to 100)")
    flags.add_argument('--start-page', '-s', type=int, default=1,
                       help="start from page N of the file listing (defaults to 1)")
    flags.add_argument('--end-page', '-e', type=int, default=None,
                       help="stop paging at page N of the file listing (defaults to not stop before the end)")
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
APPLICATION_NAME = 'Copy Google Drive Folders'


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
                                   'drive-copy-google-folders.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, args)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        log.info('Storing credentials to ' + credential_path)
    return credentials


def ensure_trailing_slash(val):
    if val[-1] != '/':
        return "{}/".format(val)
    return val


def main():
    """
    Copy a folder from Source to Target

    """

    log_filename = os.path.join(
        args.log_dir,
        'copy-google-drive-folder-{}.log'.format(os.path.basename(time.strftime('%Y%m%d-%H%M%S')))
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

            # get the files in the specified folder.
            files = drive_service.files()
            request = files.list(
                pageSize=args.page_size,
                q="'{}' in parents".format(args.source_folder_id),
                fields="nextPageToken, files(id, name, mimeType)"
            )

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
                        log.info(u"#== Processing {} {} file number {} on page {}. {} files processed.".format(
                            this_file['mimeType'],
                            this_file['name'],
                            page_file_counter,
                            page_counter,
                            file_counter
                        ))

                        # if not a folder
                        if this_file['mimeType'] != 'application/vnd.google-apps.folder':
                            # Copy the file
                            new_file = {'title': this_file['name']}
                            copied_file = drive_service.files().copy(fileId=this_file['id'], body=new_file).execute()
                            # move it to it's new location
                            drive_service.files().update(
                                fileId=copied_file['id'],
                                addParents=args.target_folder_id,
                                removeParents=args.source_folder_id
                            ).execute()
                        else:
                            log.info(u"Skipped Folder")

                else:
                    log.info(u"Skipping Page {}".format(page_counter))

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
