#!/usr/bin/python

import os
import sys
import argparse
import subprocess
import yaml
import mimetypes

from drive import GoogleDrive, DRIVE_RW_SCOPE

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--config', '-f', default='gd.conf')
    p.add_argument('--text', '-T', action='store_const', const='text/plain',
            dest='mime_type')
    p.add_argument('--html', '-H', action='store_const', const='text/html',
            dest='mime_type')
    p.add_argument('--mime-type', dest='mime_type')
    p.add_argument('--ext', dest='ext',
            help='find the default mime-type according to this ext')
    p.add_argument('--raw', '-R', action='store_true',
            help='Download original document if possible.')
    p.add_argument('--repository-name', dest='repository_name')
    p.add_argument('--file-name', dest='file_name')

    p.add_argument('docid')

    return p.parse_args()

def mapIfDefined(fn, value):
    return fn(value) if value is not None else None

def mime_type_ext(mime_type):
    if (mime_type == 'text/plain'):
        return 'txt'
    else:
        return mapIfDefined(lambda str:str[1:], mimetypes.guess_extension(mime_type))

def main():
    opts = parse_args()
    mimetypes.init()
    
    if opts.ext:
        if opts.mime_type:
            print "Specify either ext or mime-type, but not both"
            exit(1)
        opts.mime_type = mimetypes.types_map['.' + opts.ext]
    
    if not opts.mime_type:
		print "Exactly one mime-type must be given!"
		exit(1)
    cfg = yaml.load(open(opts.config))
    gd = GoogleDrive(
            client_id=cfg['googledrive']['client id'],
            client_secret=cfg['googledrive']['client secret'],
            scopes=[DRIVE_RW_SCOPE],
            )

    # Establish our credentials.
    gd.authenticate()

    # Get information about the specified file.  This will throw
    # an exception if the file does not exist.
    md = gd.get_file_metadata(opts.docid)

    mime_types = md['exportLinks'].keys()
    print 'mime types available: %s' % map(str, mime_types)
    print 'exts available: %s' % map(mime_type_ext, mime_types)

    repository_name = opts.repository_name or md['title']
    ext = opts.ext or mime_type_ext(opts.mime_type)
    file_name = opts.file_name or (md['title'] + ('.' + ext if ext is not None else ""))
    
    # Initialize the git repository.
    print 'Create repository "%s"' % repository_name
    subprocess.call(['git','init',repository_name])
    os.chdir(repository_name)

    # Iterate over the revisions (from oldest to newest).
    for rev in gd.revisions(opts.docid):
        with open(file_name, 'w') as fd:
            if 'exportLinks' in rev and not opts.raw:
                # If the file provides an 'exportLinks' dictionary,
                # download the requested MIME type.
                r = gd.session.get(rev['exportLinks'][opts.mime_type])
            elif 'downloadUrl' in rev:
                # Otherwise, if there is a downloadUrl, use that.
                r = gd.session.get(rev['downloadUrl'])
            else:
                raise KeyError('unable to download revision')

            # Write file content into local file.
            for chunk in r.iter_content():
                fd.write(chunk)

        # Commit changes to repository.
        subprocess.call(['git', 'add', file_name])
        subprocess.call(['git', 'commit', '-m',
            'revision from %s' % rev['modifiedDate']])

if __name__ == '__main__':
    main()
