from django.core.management.base import BaseCommand

from documents.models import DocumentType, Requirement

DATA = {
    "Barangay Clearance": (100, "Proof of good standing in the barangay.", [
        ("Valid ID", "Any government-issued ID", True),
        ("Proof of Residency", "Utility bill or lease contract", True),
    ]),
    "Certificate of Residency": (50, "Certifies that you live in the barangay.", [
        ("Valid ID", "Any government-issued ID", True),
        ("Proof of Residency", "Utility bill or lease contract", False),
    ]),
    "Certificate of Indigency": (0, "For residents needing financial or medical assistance.", [
        ("Valid ID", "Any government-issued ID", True),
        ("Supporting Document", "Medical certificate or referral letter", False),
    ]),
}


class Command(BaseCommand):
    help = "Create the default barangay document types and their requirements."

    def handle(self, *args, **options):
        for name, (fee, desc, reqs) in DATA.items():
            doc_type, created = DocumentType.objects.get_or_create(
                name=name, defaults={"fee": fee, "description": desc})
            if created:
                for rname, rdesc, mandatory in reqs:
                    Requirement.objects.create(document_type=doc_type, name=rname,
                                               description=rdesc, is_mandatory=mandatory)
            self.stdout.write(f"{'Created' if created else 'Exists '}: {name}")
