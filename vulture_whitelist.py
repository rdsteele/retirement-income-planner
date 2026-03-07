# vulture_whitelist.py
# False positives to suppress. Common sources:
#   - Dataclass fields accessed via FastAPI/Pydantic serialization
#   - FastAPI route functions registered via decorator (never called directly)
#   - Enum members referenced by string in API responses
#
# At --min-confidence 80 this codebase currently has zero findings.
# This file is a placeholder so the CI invocation
#   vulture services/ api/ vulture_whitelist.py --min-confidence 80
# has a stable path to add entries as the codebase grows.
