# PURPOSE: Parse the Option A text blocks into the per-course dict.

# TODO: def parse_courses_text_to_dict(raw_text: str):
#   - split on blank lines -> blocks
#   - for each block:
#       * first line: "COURSE | Prof: NAME" (prof optional)
#           - regex r'^\s*([A-Za-z0-9\- ]+)(?:\s*\|\s*Prof:\s*(.+))?\s*$'
#           - course = uppercase + trimmed
#       * following non-empty lines -> topics list (max ~10)
#   - dedupe by course (merge topics, dedupe topics)
#   - build: { course: {"professor": name_or_empty, "desc": topics, "volunteers": []} }
#   - return (courses_dict, errors_list)

# TODO: def slugify_course(course: str) -> str:
#   - uppercase; replace non-alnum with '-' ; collapse repeats; trim
