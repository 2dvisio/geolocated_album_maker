#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from iptcinfo3 import IPTCInfo
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from collections import defaultdict
from datetime import datetime
import argparse
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import json


def get_exif_data(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if not exif_data:
            return None

        exif = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            exif[tag] = value

        return exif
    except Exception as e:
        print(f"Error reading EXIF from {image_path}: {e}")
        return None


def get_iptc_people(image_path, cache=None):
    cache_key = str(image_path)

    if cache and cache_key in cache:
        return cache[cache_key]

    try:
        from PIL import Image
        from PIL.IptcImagePlugin import getiptcinfo

        image = Image.open(image_path)
        iptc_data = getiptcinfo(image)
        people = []

        if iptc_data:
            # IPTC tag (2, 25) is Keywords
            if (2, 25) in iptc_data:
                keywords = iptc_data[(2, 25)]
                if isinstance(keywords, bytes):
                    keywords = [keywords]
                for kw in keywords:
                    if isinstance(kw, bytes):
                        people.append(kw.decode('utf-8', errors='ignore'))
                    else:
                        people.append(str(kw))

            # IPTC tag (2, 80) is By-line (creator/person)
            if (2, 80) in iptc_data:
                byline = iptc_data[(2, 80)]
                if isinstance(byline, bytes):
                    people.append(byline.decode('utf-8', errors='ignore'))
                else:
                    people.append(str(byline))

        # Fallback to IPTCInfo library
        if not people:
            try:
                iptc = IPTCInfo(image_path, force=True)
                if hasattr(iptc, 'keywords') and iptc.keywords:
                    for keyword in iptc.keywords:
                        kw_str = keyword.decode('utf-8', errors='ignore') if isinstance(keyword, bytes) else str(keyword)
                        if kw_str not in people:
                            people.append(kw_str)
            except:
                pass

        if people:
            print(f"Found people in {image_path}: {people}")

        result = people if people else None
        if cache is not None:
            cache[cache_key] = result

        return result
    except Exception as e:
        print(f"Error reading IPTC from {image_path}: {e}")
        if cache is not None:
            cache[cache_key] = None
        return None


def get_gps_info(exif_data):
    if not exif_data or 'GPSInfo' not in exif_data:
        return None

    gps_info = {}
    for key in exif_data['GPSInfo'].keys():
        decode = GPSTAGS.get(key, key)
        gps_info[decode] = exif_data['GPSInfo'][key]

    return gps_info


def convert_to_degrees(value):
    d, m, s = value
    return d + (m / 60.0) + (s / 3600.0)


def get_coordinates(gps_info):
    if not gps_info:
        return None

    try:
        lat = convert_to_degrees(gps_info['GPSLatitude'])
        if gps_info['GPSLatitudeRef'] == 'S':
            lat = -lat

        lon = convert_to_degrees(gps_info['GPSLongitude'])
        if gps_info['GPSLongitudeRef'] == 'W':
            lon = -lon

        return (lat, lon)
    except Exception as e:
        print(f"Error converting coordinates: {e}")
        return None


def load_geocache(cache_file='.geocache.json'):
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading geocache: {e}")
    return {}


def save_geocache(cache, cache_file='.geocache.json'):
    try:
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Error saving geocache: {e}")


def load_people_cache(cache_file='.peoplecache.json'):
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading people cache: {e}")
    return {}


def save_people_cache(cache, cache_file='.peoplecache.json'):
    try:
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Error saving people cache: {e}")


def get_location_name(lat, lon, cache=None):
    cache_key = f"{lat:.4f},{lon:.4f}"

    if cache and cache_key in cache:
        return cache[cache_key]

    try:
        geolocator = Nominatim(user_agent="photo_location_pdf")
        time.sleep(1)
        location = geolocator.reverse(f"{lat}, {lon}", language='en', timeout=10)

        location_name = None
        if location and location.raw.get('address'):
            address = location.raw['address']

            city = (address.get('city') or
                   address.get('town') or
                   address.get('village') or
                   address.get('municipality') or
                   address.get('county'))

            country = address.get('country', '')

            if city and country:
                location_name = f"{city}, {country}"
            elif city:
                location_name = city
            elif country:
                location_name = country

        if not location_name:
            location_name = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"

        if cache is not None:
            cache[cache_key] = location_name

        return location_name

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error: {e}. Using coordinates instead.")
        location_name = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
        if cache is not None:
            cache[cache_key] = location_name
        return location_name
    except Exception as e:
        print(f"Unexpected error in geocoding: {e}")
        location_name = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
        if cache is not None:
            cache[cache_key] = location_name
        return location_name


def cluster_locations(photos, threshold=0.01):
    clusters = []

    for photo in photos:
        lat, lon = photo['coordinates']
        found_cluster = False

        for cluster in clusters:
            cluster_lat, cluster_lon = cluster['center']
            if abs(lat - cluster_lat) < threshold and abs(lon - cluster_lon) < threshold:
                cluster['photos'].append(photo)
                avg_lat = sum(p['coordinates'][0] for p in cluster['photos']) / len(cluster['photos'])
                avg_lon = sum(p['coordinates'][1] for p in cluster['photos']) / len(cluster['photos'])
                cluster['center'] = (avg_lat, avg_lon)
                found_cluster = True
                break

        if not found_cluster:
            clusters.append({
                'center': (lat, lon),
                'photos': [photo]
            })

    return clusters


def get_image_date(exif_data):
    if not exif_data:
        return None

    for tag in ['DateTimeOriginal', 'DateTime', 'DateTimeDigitized']:
        if tag in exif_data:
            try:
                return datetime.strptime(exif_data[tag], '%Y:%m:%d %H:%M:%S')
            except:
                pass
    return None


def create_pdf(year_groups, output_path, geocache, peoplecache):
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                          topMargin=0.5*inch, bottomMargin=0.5*inch,
                          leftMargin=0.5*inch, rightMargin=0.5*inch)

    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#2c3e50',
        spaceAfter=30,
        alignment=TA_CENTER
    )

    year_style = ParagraphStyle(
        'YearTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor='#1a252f',
        spaceAfter=20,
        spaceBefore=30,
        alignment=TA_CENTER
    )

    location_style = ParagraphStyle(
        'LocationTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='#34495e',
        spaceAfter=12,
        spaceBefore=20
    )

    caption_style = ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontSize=7,
        textColor='#7f8c8d',
        alignment=TA_CENTER
    )

    story.append(Paragraph("Photo Album by Year and Location", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    first_year = True
    for year, clusters in sorted(year_groups.items()):
        if not first_year:
            story.append(PageBreak())
        first_year = False

        story.append(Paragraph(str(year), year_style))
        story.append(Spacer(1, 0.2*inch))

        for i, cluster in enumerate(clusters, 1):
            lat, lon = cluster['center']
            print(f"\nLooking up location for {year} cluster {i}...")
            location_name = get_location_name(lat, lon, geocache)

            story.append(Paragraph(f"{location_name}", location_style))
            story.append(Paragraph(f"{len(cluster['photos'])} photo(s)", styles['Normal']))
            story.append(Spacer(1, 0.15*inch))

            photos = cluster['photos']
            img_size = 2.3 * inch

            grid_data = []
            current_row = []

            for idx, photo in enumerate(photos):
                try:
                    img = RLImage(photo['path'])
                    aspect = img.imageWidth / img.imageHeight

                    if aspect > 1:
                        img.drawWidth = img_size
                        img.drawHeight = img_size / aspect
                    else:
                        img.drawHeight = img_size
                        img.drawWidth = img_size * aspect

                    caption_parts = []
                    if photo['date']:
                        caption_parts.append(photo['date'].strftime('%b %d, %Y'))
                    if photo.get('people'):
                        caption_parts.append(', '.join(photo['people']))
                    caption_text = '<br/>'.join(caption_parts)

                    cell_content = [img, Paragraph(caption_text, caption_style)]
                    current_row.append(cell_content)

                    if len(current_row) == 3:
                        grid_data.append(current_row)
                        current_row = []

                except Exception as e:
                    print(f"Error adding image {photo['path']}: {e}")

            if current_row:
                while len(current_row) < 3:
                    current_row.append("")
                grid_data.append(current_row)

            if grid_data:
                table = Table(grid_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
                table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ]))
                story.append(table)

                if i < len(clusters):
                    story.append(Spacer(1, 0.3*inch))

    doc.build(story)
    save_geocache(geocache)
    save_people_cache(peoplecache)
    print(f"\nPDF created successfully: {output_path}")


def process_images(input_path, output_path, threshold):
    photos = []
    geocache = load_geocache()
    peoplecache = load_people_cache()

    input_path = Path(input_path)

    if input_path.is_file():
        image_files = [input_path]
    elif input_path.is_dir():
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG', '*.png', '*.PNG']:
            image_files.extend(input_path.glob(ext))
    else:
        print(f"Error: {input_path} is not a valid file or directory")
        return

    print(f"Found {len(image_files)} image(s) to process...")
    print(f"Loaded {len(geocache)} cached location(s)")
    print(f"Loaded {len(peoplecache)} cached people tag(s)")

    for image_path in image_files:
        exif_data = get_exif_data(str(image_path))
        gps_info = get_gps_info(exif_data)
        coordinates = get_coordinates(gps_info)

        if coordinates:
            photo_date = get_image_date(exif_data)
            people = get_iptc_people(str(image_path), peoplecache)
            photos.append({
                'path': str(image_path),
                'coordinates': coordinates,
                'date': photo_date,
                'year': photo_date.year if photo_date else None,
                'people': people
            })
            lat, lon = coordinates
            cache_key = f"{lat:.4f},{lon:.4f}"
            location_str = geocache.get(cache_key, f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}")
            print(f"✓ {image_path.name} - GPS: {location_str}")
        else:
            print(f"✗ {image_path.name} - No GPS data found")

    if not photos:
        print("\nNo photos with GPS data found!")
        return

    print(f"\nProcessing {len(photos)} photo(s) with GPS data...")

    year_groups = defaultdict(list)
    for photo in photos:
        year = photo['year'] if photo['year'] else 'Unknown'
        year_groups[year].append(photo)

    for year, year_photos in year_groups.items():
        clusters = cluster_locations(year_photos, threshold)
        clusters.sort(key=lambda c: len(c['photos']), reverse=True)

        for cluster in clusters:
            cluster['photos'].sort(key=lambda p: p['date'] if p['date'] else datetime.min)

        year_groups[year] = clusters

    total_clusters = sum(len(clusters) for clusters in year_groups.values())
    print(f"Grouped into {len(year_groups)} year(s) and {total_clusters} location(s)")

    create_pdf(year_groups, output_path, geocache, peoplecache)


def main():
    parser = argparse.ArgumentParser(
        description='Create a PDF document from photos grouped by GPS location',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python photo_location_pdf.py /path/to/photos output.pdf
  python photo_location_pdf.py /path/to/photos output.pdf --threshold 0.05
  python photo_location_pdf.py single_photo.jpg output.pdf
        """
    )

    parser.add_argument('input', help='Path to image file or directory containing images')
    parser.add_argument('output', help='Output PDF file path')
    parser.add_argument('--threshold', type=float, default=0.01,
                       help='Location clustering threshold in degrees (default: 0.01, ~1km)')

    args = parser.parse_args()

    if not args.output.lower().endswith('.pdf'):
        args.output += '.pdf'

    process_images(args.input, args.output, args.threshold)


if __name__ == '__main__':
    main()
