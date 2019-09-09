#!/usr/bin/env python

import html
import os
import pprint
import requests
import youtube_dl

from bs4 import BeautifulSoup
from copy import copy
from PyPDF2 import PdfFileReader, PdfFileWriter

from ricecooker.chefs import SushiChef
from ricecooker.classes.nodes import ChannelNode, TopicNode, DocumentNode
from ricecooker.classes.files import DocumentFile
from ricecooker.classes.licenses import get_license
from ricecooker.utils.pdf import PDFParser

LANG_CODE_EN = 'en'
LANG_CODE_MY = 'my'
LANG_CODES = (LANG_CODE_EN, LANG_CODE_MY,)

POINTB_URL = 'http://www.pointb.is/'

DOWNLOADS_PATH = "downloads/"
PDF_SPLIT_PATH = ''.join([DOWNLOADS_PATH, '/21CSGuide_English_split/'])

POINTB_PDF_URL = ''.join([POINTB_URL, 's/'])
CSGUIDE_PDF_EN = '21CSGuide_English.pdf'
CSGUIDE_PDF_EN_CROPPED = '21CSGuide_English_cropped.pdf'
CSGUIDE_PDF_MY = '21CSGuide_Myanmar.pdf'
CSGUIDE_PDF_MY_CROPPED = '21CSGuide_Myanmar_cropped.pdf'
PDF_URL_EN = ''.join([POINTB_PDF_URL, CSGUIDE_PDF_EN])
PDF_URL_MY = ''.join([POINTB_PDF_URL, CSGUIDE_PDF_MY])
PDF_PATH_EN = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN)
PDF_PATH_EN_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_EN_CROPPED)
PDF_PATH_MY = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY)
PDF_PATH_MY_CROPPED = os.path.join(os.getcwd(), DOWNLOADS_PATH, CSGUIDE_PDF_MY_CROPPED)
PDFS = (
    {'pdf_url': PDF_URL_EN, 'pdf_path': PDF_PATH_EN},
    # { 'pdf_url': PDF_URL_MY, 'pdf_path': PDF_PATH_MY },
)

VIDEO_URL_EN = ''.join([POINTB_URL, '21cs-videos'])
VIDEO_URL_MY = ''.join([POINTB_URL, '21cs-videos-mm'])
VIDEO_FILENAME_PREFIX_EN = 'pointb21cs-video-%s-' % LANG_CODE_EN
VIDEO_FILENAME_PREFIX_MY = 'pointb21cs-video-%s-' % LANG_CODE_MY
VIDEO_URLS = (
    {
        'video_url': VIDEO_URL_EN, 
        'filename_prefix': VIDEO_FILENAME_PREFIX_EN,
        'lang_code': LANG_CODE_EN
    },
    {
        'video_url': VIDEO_URL_MY, 
        'filename_prefix': VIDEO_FILENAME_PREFIX_MY,
        'lang_code': LANG_CODE_MY
    },
)


def split_chapters_en():
    """
    Splits the chapters for the English PDF.
    """
    print('==> Splitting chapters for', PDF_PATH_EN_CROPPED)

    page_ranges = [
        {'title': 'Front Matter', 'page_start': 0, 'page_end': 13},
        {'title': 'Section 1 - Setting a Vision for Your 21st Century Learning Classroom', 'page_start': 13, 'page_end': 21},
        {'title': 'Section 2 - 21st Century Mindsets and Practices', 'page_start': 21, 'page_end': 61,
        'children': [
            {'title': 'Mindset #1: Mindfulness', 'page_start': 23, 'page_end': 31},
            {'title': 'Mindset #2: Curiousity', 'page_start': 31, 'page_end': 37},
            {'title': 'Mindset #3: Growth', 'page_start': 37, 'page_end': 41},
            {'title': 'Mindset #4: Empathy', 'page_start': 41, 'page_end': 47},
            {'title': 'Mindset #5: Appreciation', 'page_start': 47, 'page_end': 51},
            {'title': 'Mindset #6: Experimentation', 'page_start': 51, 'page_end': 57},
            {'title': 'Mindset #7: Systems Thinking', 'page_start': 57, 'page_end': 61}
        ]
        },
        {'title': 'Section 3 - 21st Century Skills', 'page_start': 61, 'page_end': 69},
        {'title': 'Section 4 - Self-Discovery', 'page_start': 69, 'page_end': 95},
        {'title': 'Section 5 - 21st Century Skills Building For Teachers', 'page_start': 95, 'page_end': 109},
        {'title': 'Section 6 - Integrating 21st Century Skills Into Your Classroom', 'page_start': 109, 'page_end': 135},
        {'title': 'Thanks To Our Teachers', 'page_start': 135, 'page_end': 137},
    ]

    with PDFParser(PDF_PATH_EN_CROPPED, directory=PDF_SPLIT_PATH) as pdfparser:
        chapters = pdfparser.split_subchapters(jsondata=page_ranges)
        # for chapter in chapters:
        #     print(chapter)

    print('==> DONE splitting chapters for English PDF.')
    return True


def download_pdfs():
    try:
        for pdf in PDFS:
            pdf_url = pdf['pdf_url']
            pdf_path = pdf['pdf_path']
            # Do not download if file already exists.
            if os.path.exists(pdf_path):
                print('==> PDF already exists, NOT downloading:', pdf_path)
            else:
                print('==> Downloading PDF', pdf_url, 'TO', pdf_path)
                response = requests.get(pdf_url)
                assert response.status_code == 200
                # save .pdf to the downloads folder
                with open(pdf_path, 'wb') as pdf_file:
                    pdf_file.write(response.content)
                print('... DONE downloading.')

            # crop from two-paged pdf into single-page pdf
            print('==> Cropping from two-page into single-page...', pdf_path)
            pdf_path_cropped = pdf_path.replace('.pdf', '_cropped.pdf')
            split_left_right_pages(pdf_path, pdf_path_cropped)

            print_pdf_info(pdf_path_cropped)

            print('... DONE cropping.')

        return True
    except Exception as exc:
        print('==> ERROR downloading PDFs: ', exc)
        return False


def get_dimensions(pdfin1):
    """
    Get dimensions of second page in PDF file `pdfin1`.
    Returns tuple: (half_width, full_height)
    """
    page = pdfin1.getPage(2)
    double_page_width = page.mediaBox.getUpperRight_x()
    page_width = double_page_width / 2
    page_height = page.mediaBox.getUpperRight_y()
    return page_width, page_height


def split_left_right_pages(pdfin_path, pdfout_path):
    """
    Splits the left and right halves of a page into separate pages.
    We also remove the binders between those separated pages.
    """
    # REF: https://gist.github.com/mdoege/0676e37ee2470fc755ea98177a560b4b
    # RELATED-REF: https://github.com/mstamy2/PyPDF2/issues/100

    pdfin1 = PdfFileReader(open(pdfin_path, "rb"))  # used for left pages
    pdfout = PdfFileWriter()

    num_pages = pdfin1.getNumPages()
    page_ranges = [pdfin1.getPage(i) for i in range(0, num_pages)]
    for nn, left_page in enumerate(page_ranges):
        # use copy for the right pages
        right_page = copy(left_page)
        # copy the existing page dimensions
        (page_width, page_height,) = left_page.mediaBox.upperRight

        is_first_page = (nn == 0)
        is_last_page = (nn + 1 >= num_pages)
        if is_first_page or is_last_page:
            # The first page has the binder to its left while the last page
            # has the binder to its right.
            binder_width = 40
            if is_first_page:
                (page_width, page_height,) = right_page.mediaBox.upperLeft
                right_page.mediaBox.upperLeft = (page_width + binder_width, page_height,)
            if is_last_page:
                (page_width, page_height,) = right_page.mediaBox.upperRight
                right_page.mediaBox.upperRight = (page_width - binder_width, page_height,)
        else:
            # Divide the width by 2 for the other pages (except first and last).
            # We also remove the binders on the left-side of the right pages
            # and the right-side of the left pages.
            page_width = page_width / 2
            binder_width = 20
            right_page.mediaBox.upperLeft = (page_width + binder_width, page_height,)
            left_page.mediaBox.upperRight = (page_width - binder_width, page_height,)
            pdfout.addPage(left_page)
        pdfout.addPage(right_page)

    with open(pdfout_path, "wb") as out_f:
        pdfout.write(out_f)


def print_pdf_info(pdf_path):
    pp = pprint.PrettyPrinter()
    pdf = PdfFileReader(open(pdf_path, "rb"))
    page_width, page_height = get_dimensions(pdf)
    print('==> PDF INFO:', page_width, page_height)
    num_pages = pdf.getNumPages()
    for page_num in range(0, num_pages):
        page = pdf.getPage(page_num)
        this_width = page.mediaBox.getUpperRight_x()
        this_height = page.mediaBox.getUpperRight_y()
        print('==> page', page_num, 'this_width',
              this_width, 'this_height', this_height)
        # pretty print the last 3 pages
        # if page_num + 3 >= num_pages:
        #     pp.pprint(page)


def local_construct_pdfs():
    # TODO(cpauya): for testing, remove when done
    if not download_pdfs():
        print('==> Download of PDFS FAILED!')
        return False

    if not split_chapters_en():
        print('==> Split chapters for English PDF FAILED!')
        return False

    main_topic = TopicNode(title="English", source_id="<21cs_en_id>")

    frontmatter_file = "0-Front-Matter.pdf"

    # Introduction
    front_doc_node = DocumentNode(
        title="Introduction",
        description="Introduction",
        source_id=frontmatter_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language=LANG_CODE_EN,
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, frontmatter_file),
                language=LANG_CODE_EN
            )
        ])
    main_topic.add_child(front_doc_node)
    return False


class PointB21Video():

    uid = 0  # unique ID
    title = ''
    description = ''
    url = ''
    lang_code = ''
    filename_prefix = ''

    def __init__(self, uid=0, url='', title='', description='', lang_code='', 
            filename_prefix=''):
        self.uid = uid  # TODO(cpauya): 
        self.url = url
        self.title = title
        self.description = description
        self.lang_code = lang_code
        self.filename_prefix = filename_prefix

    def __str__(self):
        return 'PointB21Video (%s - %s - %s)' % (self.uid, self.title, self.url,)

    def get_filename(self):
        return self.filename_prefix + '%(id)s.%(ext)s'

    def download(self):
        ydl_options = {
            'outtmpl': self.get_filename(),
            'writethumbnail': True,
            'no_warnings': True,
            'continuedl': False,
            'restrictfilenames': True,
            'quiet': False,
            # Note the format specification is important so we get mp4 and not taller than 480
            'format': "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]"
        }
        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            pp = pprint.PrettyPrinter()
            try:
                ydl.add_default_info_extractors()
                vinfo = ydl.extract_info(self.url, download=True)
                # Replace "temporary values" of attributes with actual values.
                self.uid = vinfo.get('id', '')
                self.title = vinfo.get('title', '')
                self.description = vinfo.get('description', '')
                print('==> video', self)

                # # These are useful when debugging.
                # del vinfo['formats']  # to keep from printing 100+ lines
                # del vinfo['requested_formats']  # to keep from printing 100+ lines
                # print('==> Printing video info:')
                # pp.pprint(vinfo)
            except (youtube_dl.utils.DownloadError,
                    youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError,) as e:
                print('==> PointB21Video.download(): Error downloading videos')
                pp.pprint(e)
                return False
        return True


def scrape_video_data(url, lang_code, filename_prefix):
    """
    Scrapes videos based on the URL passed and returns a list of PointB21Video objects.
    For efficiency, the actual download will be done outside of this function, 
    after all video links have been collected.
    """
    video_data = []
    try:
        if lang_code in LANG_CODES:
            print('==> SCRAPING', url)
            response = requests.get(url)
            page = BeautifulSoup(response.text, 'html5lib')

            content_divs = page.find_all('div', class_='content-inner')
            for content_div in content_divs:
                video_block = content_div.find('div', class_='video-block')
                video_wrapper = video_block.find('div', class_='sqs-video-wrapper')
                data_html_raw = video_wrapper['data-html']
                data_html = html.unescape(data_html_raw)
                chunk = BeautifulSoup(data_html, 'html5lib')
                iframe = chunk.find('iframe')
                src = iframe['src']
                title = 'TODO:'
                description = 'TODO:'
                video = PointB21Video(
                            url=src, 
                            title=title, 
                            description=description, 
                            lang_code=lang_code,
                            filename_prefix=filename_prefix)
                video_data.append(video)
    except Exception as e:
        print('==> Error scraping video URL', VIDEO_URL_EN)
        pp = pprint.PrettyPrinter()
        pp.pprint(e)
    return video_data


def download_videos():
    """
    Actually download the videos.
    TODO(cpauya): Download videos to the `downloads/videos/` folder.
    """
    for vinfo in VIDEO_URLS:
        try:
            video_data = scrape_video_data(
                                vinfo['video_url'], 
                                vinfo['lang_code'], 
                                vinfo['filename_prefix'])
            print('==> DOWNLOADING', vinfo)
            # Do the actual download of video and metadata info for all video objects.
            for i, video in enumerate(video_data):
                progress = '%d/%d' % (i+1, len(video_data),)
                progress = '==> %s: Downloading video from %s ...' % (progress, video.url,)
                print(progress)
                if video.download():
                    # TODO(cpauya): Create VideoTopic then add to channel.
        except Exception as e:
            print('Error downloading videos:')
            pp = pprint.PrettyPrinter()
            pp.pprint(e)
        print('==> DONE downloading videos for', vinfo)
    print('==> DONE downloading videos!')
    return True


def local_construct_videos():
    """
    TODO(cpauya): for testing, remove when done
    """
    if not download_videos():
        print('==> Download of Videos FAILED!')
        return False

    # main_topic = TopicNode(title="English", source_id="<21cs_en_id>")

    # # Introduction
    # front_doc_node = DocumentNode(
    #     title="Introduction",
    #     description="Introduction",
    #     source_id=frontmatter_file,
    #     license=get_license("CC BY-NC-SA", copyright_holder="Point B Design and Training"),
    #     language="en",
    #     files=[
    #         DocumentFile(
    #             path=os.path.join(PDF_SPLIT_PATH, frontmatter_file),
    #             language="en"
    #         )
    #     ])
    # main_topic.add_child(front_doc_node)
    return False


def build_english_pdf_topics(main_topic):

    frontmatter_file = "0-Front-Matter.pdf"
    section_1_file = "1-Section-1---Setting-a-Vision-for-Your-21st-Century-Learning-Classroom.pdf"
    section_2_file = "2-Section-2---21st-Century-Mindsets-and-Practices.pdf"
    section_2_0_file = "2-0-Mindset-1-Mindfulness.pdf"
    section_2_1_file = "2-1-Mindset-2-Curiousity.pdf"
    section_2_2_file = "2-2-Mindset-3-Growth.pdf"
    section_2_3_file = "2-3-Mindset-4-Empathy.pdf"
    section_2_4_file = "2-4-Mindset-5-Appreciation.pdf"
    section_2_5_file = "2-5-Mindset-6-Experimentation.pdf"
    section_2_6_file = "2-6-Mindset-7-Systems-Thinking.pdf"
    section_3_file = "3-Section-3---21st-Century-Skills.pdf"
    section_4_file = "4-Section-4---Self-Discovery.pdf"
    section_5_file = "5-Section-5---21st-Century-Skills-Building-For-Teachers.pdf"
    section_6_file = "6-Section-6---Integrating-21st-Century-Skills-Into-Your-Classroom.pdf"
    section_7_file = "7-Thanks-To-Our-Teachers.pdf"

    # Introduction
    front_doc_node = DocumentNode(
        title="Introduction",
        description="Introduction",
        source_id=frontmatter_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, frontmatter_file),
                language="en"
            )
        ])
    main_topic.add_child(front_doc_node)

    # Section 1
    section_1_doc_node = DocumentNode(
        title="Section 1",
        description="Section 1: Setting a Vision for Your 21st Century Learning Classroom",
        source_id=section_1_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_1_file),
                language="en"
            )
        ])
    main_topic.add_child(section_1_doc_node)

    # Section 2
    section_2_topic = TopicNode(
        title="21st Century Mindsets & Practices",
        source_id="21cs_section_2")

    section_2_doc_node = DocumentNode(
        title="21st Century Mindsets and Practices",
        description="21st Century Mindsets and Practices",
        source_id=section_2_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_doc_node)

    section_2_0_doc_node = DocumentNode(
        title="Mindset #1: Mindfulness",
        description="Mindset #1: Mindfulness",
        source_id=section_2_0_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_0_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_0_doc_node)

    section_2_1_doc_node = DocumentNode(
        title="Mindset #2: Curiousity",
        description="Mindset #2: Curiousity",
        source_id=section_2_1_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_1_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_1_doc_node)

    section_2_2_doc_node = DocumentNode(
        title="Mindset #3: Growth",
        description="Mindset #3: Growth",
        source_id=section_2_2_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_2_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_2_doc_node)

    section_2_3_doc_node = DocumentNode(
        title="Mindset #4: Empathy",
        description="Mindset #4: Empathy",
        source_id=section_2_3_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_3_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_3_doc_node)

    section_2_4_doc_node = DocumentNode(
        title="Mindset #5: Appreciation",
        description="Mindset #5: Appreciation",
        source_id=section_2_4_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_4_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_4_doc_node)

    section_2_5_doc_node = DocumentNode(
        title="Mindset #6: Experimentation",
        description="Mindset #6: Experimentation",
        source_id=section_2_5_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_5_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_5_doc_node)

    section_2_6_doc_node = DocumentNode(
        title="Mindset #7: Systems Thinking",
        description="Mindset #7: Systems Thinking",
        source_id=section_2_6_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_2_6_file),
                language="en"
            )
        ])
    section_2_topic.add_child(section_2_6_doc_node)
    main_topic.add_child(section_2_topic)

    # Section 3
    section_3_doc_node = DocumentNode(
        title="Section 3",
        description="Section 3: 21st Century Skills",
        source_id=section_3_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_3_file),
                language="en"
            )
        ])
    main_topic.add_child(section_3_doc_node)

    # Section 4
    section_4_doc_node = DocumentNode(
        title="Section 4",
        description="Section 4: Self Discovery",
        source_id=section_4_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_4_file),
                language="en"
            )
        ])
    main_topic.add_child(section_4_doc_node)

    # Section 5
    section_5_doc_node = DocumentNode(
        title="Section 5",
        description="Section 5: 21st Century Skills Building For Teachers",
        source_id=section_5_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_5_file),
                language="en"
            )
        ])
    main_topic.add_child(section_5_doc_node)

    # Section 6
    section_6_doc_node = DocumentNode(
        title="Section 6",
        description="Section 6: Integrating 21st Century Skills Into Your Classroom",
        source_id=section_6_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_6_file),
                language="en"
            )
        ])
    main_topic.add_child(section_6_doc_node)

    # Section 7
    section_7_doc_node = DocumentNode(
        title="Section 7",
        description="Section 7: Thanks To Our Teachers",
        source_id=section_7_file,
        license=get_license(
            "CC BY-NC-SA", copyright_holder="Point B Design and Training"),
        language="en",
        files=[
            DocumentFile(
                path=os.path.join(PDF_SPLIT_PATH, section_7_file),
                language="en"
            )
        ])
    main_topic.add_child(section_7_doc_node)
    return main_topic


def build_english_video_topics(main_topic):
    return main_topic


def build_burmese_pdf_topics(main_topic):
    return main_topic


def build_burmese_video_topics(main_topic):
    return main_topic


class PointBChef(SushiChef):
    channel_info = {
        "CHANNEL_TITLE": "PointB 21CS Guide",
        # where you got the content (change me!!)
        "CHANNEL_SOURCE_DOMAIN": "pointb.is",
        # channel's unique id (change me!!) # TODO(cpauya): remove 'test-'
        "CHANNEL_SOURCE_ID": "test-21csguide",
        "CHANNEL_LANGUAGE": "mul",  # le_utils language code
        "CHANNEL_THUMBNAIL": None,  # TODO(cpauya): set thumbnail
        # (optional)
        "CHANNEL_DESCRIPTION": "Guide To Becoming A 21St Century Teacher",
    }

    def construct_channel(self, **kwargs):

        if not download_pdfs():
            print('==> Download of PDFS FAILED!')
            return False

        if not split_chapters_en():
            print('==> Split chapters for English PDF FAILED!')
            return False

        channel = self.get_channel(**kwargs)

        main_topic = TopicNode(title="English", source_id="<21cs_en_id>")
        main_topic2 = TopicNode(title="Burmese", source_id="<21cs_my_id>")
        channel.add_child(main_topic)
        channel.add_child(main_topic2)

        main_topic = build_english_pdf_topics(main_topic)
        # TODO(cpauya): English videos
        main_topic = build_english_video_topics(main_topic)
        # TODO(cpauya): Burmese .pdfs
        main_topic = build_burmese_pdf_topics(main_topic)
        # TODO(cpauya): Burmese videos
        main_topic = build_burmese_video_topics(main_topic)

        return channel


if __name__ == "__main__":
    """
    Run this script on the command line using:
        python sushichef.py -v --reset --token=YOURTOKENHERE9139139f3a23232
    """
    # chef = PointBChef()
    # chef.main()
    # local_construct_pdfs()
    local_construct_videos()
