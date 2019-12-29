#!/usr/bin/env python3

import pyexiv2
import os
import argparse
import logging
import re
import pathlib
import shutil
import datetime
import hashlib
import random
import string

IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.gif')
VIDEO_EXT = ('.mts', '.mp4', '.avi')

logger = logging.getLogger('picrename')

# Calculate regex for data string beforehand
datere = re.compile(r"([0-9]{8})_[0-9]{6}\.")


# Generate a random string
def rand_str(length=5):
    letters = string.ascii_lowercase + string.digits
    return ''.join((random.choice(letters) for i in range(length)))


# Get MD5 sum for a file
def get_md5sum(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def compare_md5sums(fnamea, fnameb):
    md5sum1 = get_md5sum(fnamea)
    md5sum2 = get_md5sum(fnameb)
    logger.debug("{} md5: {}".format(fnamea, md5sum1))
    logger.debug("{} md5: {}".format(fnameb, md5sum2))
    return md5sum1 == md5sum2


def infer_image_dest_folder(dir, file):
    image = pyexiv2.Image(os.path.join(dir, file))
    exif_data = image.read_exif()
    if exif_data and 'Exif.Image.DateTime' in exif_data:
        y, m, _ = exif_data['Exif.Image.DateTime'].split(':', 2)
        destdir = "{}-{}".format(y, m)
    elif exif_data and 'Exif.Photo.DateTimeOriginal' in exif_data:
        y, m, _ = exif_data['Exif.Photo.DateTimeOriginal'].split(':', 2)
        destdir = "{}-{}".format(y, m)
    else:
        match = re.search(datere, file)
        if match:
            dt = match.group(1)
            destdir = "{}-{}".format(dt[:4], dt[4:6])
            logger.debug("No creation data in exif: %s" % os.path.join(dir, file))
        else:
            destdir = "unknown"
            logger.debug("Cannot find creation data for: %s" % os.path.join(dir, file))
    return destdir


def infer_video_dest_folder(dir, file):
    match = re.search(datere, file)
    if match:
        dt = match.group(1)
        destdir = "{}-{}".format(dt[:4], dt[4:6])
    else:
        logger.debug("Cannot find creation time, will use file timestamp: %s" % os.path.join(dir, file))
        # Infer the folder from file timestam
        # in linux ctime is not the creation time, mtime is the best candidate...
        fullpath = os.path.join(dir, file)
        stat_info = os.stat(fullpath)
        dt = datetime.date.fromtimestamp(stat_info.st_mtime)
        destdir = "{:04d}-{:02d}".format(dt.year, dt.month)
    return destdir


def walk_src_dir(directory, file_type):

    if file_type == "image":
        ext_list = IMAGE_EXT
    else:
        ext_list = VIDEO_EXT

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(ext_list):
                logger.debug("Looking at {}/{}".format(root, file))
                try:
                    if file_type == "image":
                        dstdir = infer_image_dest_folder(root, file)
                    else:
                        dstdir = infer_video_dest_folder(root, file)
                    yield root, file, dstdir
                except Exception as e:
                    logger.error("Cannot process image {}: {}".format(os.path.join(root, file), e))


def main():
    # create logger
    logger.setLevel(logging.DEBUG)
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    parser = argparse.ArgumentParser()
    parser.add_argument("src", help="Source directory")
    parser.add_argument("dst", help="Destination directory")
    parser.add_argument("-t", "--type", default="image", help="Specify type of files to look for (image|video)")
    args = parser.parse_args()
    logger.debug("Src:%s" % args.src)
    logger.debug("Dst:%s" % args.dst)

    nfiles = 0
    cfiles = 0

    try:
        createdSubdirs = {}
        pathlib.Path(args.dst).mkdir(parents=True, exist_ok=True)

        for srcdir, file, dstpart in walk_src_dir(args.src, args.type):
            nfiles += 1
            if dstpart not in createdSubdirs:
                pathlib.Path(args.dst, dstpart).mkdir(parents=True, exist_ok=True)
                createdSubdirs[dstpart] = True

            srcpath = pathlib.Path(srcdir, file)
            dstpath = pathlib.Path(args.dst, dstpart, file)
            if dstpath.exists():
                logger.debug("File already exists '{}'".format(dstpath))
                if not compare_md5sums(srcpath, dstpath):
                    logger.debug("MD5 sums are different. Will copy with different name.")
                    prefix = rand_str()
                    newdstpath = pathlib.Path(args.dst, dstpart, "{}-{}".format(prefix, file))
                    shutil.copy2(srcpath, newdstpath)
            else:
                shutil.copy2(srcpath, dstpath)
                cfiles += 1
    except Exception as e:
        logger.error("Failed:", e)

    logger.info("=== Files found:  {}".format(nfiles))
    logger.info("=== Files copied: {}".format(cfiles))


if __name__ == '__main__':
    main()
