from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(".")

def check_split(split):
    image_dir = ROOT / split / "images"
    xml_dir = ROOT / split / "annotations"

    images = {
        p.stem: p
        for p in image_dir.rglob("*")
        if p.suffix.lower() in [".jpg", ".jpeg", ".png"]
    }

    xmls = {
        p.stem: p
        for p in xml_dir.glob("*.xml")
    }

    missing_xml = set(images) - set(xmls)
    missing_image = set(xmls) - set(images)

    invalid_xml = []
    invalid_boxes = []

    for stem, xml_path in xmls.items():
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            objects = root.findall("object")

            if not objects:
                invalid_xml.append((stem, "Không có object"))

            for obj in objects:
                name = obj.findtext("name")
                box = obj.find("bndbox")

                if not name or box is None:
                    invalid_xml.append((stem, "Thiếu label/bndbox"))
                    continue

                coords = [
                    box.findtext("xmin"),
                    box.findtext("ymin"),
                    box.findtext("xmax"),
                    box.findtext("ymax")
                ]

                try:
                    xmin, ymin, xmax, ymax = map(float, coords)

                    if xmin >= xmax or ymin >= ymax:
                        invalid_boxes.append(stem)
                except (ValueError, TypeError):
                    invalid_xml.append((stem, "Tọa độ không hợp lệ"))

        except ET.ParseError:
            invalid_xml.append((stem, "XML bị lỗi"))

    print(f"\n===== {split.upper()} =====")
    print("Số ảnh:", len(images))
    print("Số XML:", len(xmls))
    print("Ảnh thiếu XML:", len(missing_xml))
    print("XML thiếu ảnh:", len(missing_image))
    print("XML lỗi:", len(invalid_xml))
    print("Bounding box lỗi:", len(invalid_boxes))

    if missing_xml:
        print("\nẢnh thiếu XML:", sorted(missing_xml))

    if missing_image:
        print("\nXML thiếu ảnh:", sorted(missing_image))

    if invalid_xml:
        print("\nXML không hợp lệ:", invalid_xml)

    if invalid_boxes:
        print("\nBounding box không hợp lệ:", invalid_boxes)


check_split("train")
check_split("validation")
