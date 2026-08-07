"""
Test the correction service with sample extracted medicines.
"""

import asyncio
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.services.correction_service import correct_medicines_batch
from app.schemas.schemas import GemmaMedicine


async def run_test_correction():
    """Test correction with the medicines from your screenshot."""
    
    # Medicines as they appear in your screenshot (with errors)
    sample_medicines = [
        GemmaMedicine(
            medicine="Hijenae",  # Misspelled
            dose="14tabs",
            frequency="Twice daily",
            duration="— days",  # Missing duration
            instructions="",
            age_range="10-24 years",  # Wrong format
        ),
        GemmaMedicine(
            medicine="Mahaccol",  # Misspelled
            dose="200mg",
            frequency="Once daily",
            duration="— days",  # Missing duration
            instructions="after doctor's prescription",
            age_range="10-24 years",  # Wrong format
        ),
        GemmaMedicine(
            medicine="Tuse-Do",  # Might be misspelled
            dose="4cc",
            frequency="Twice daily",
            duration="— days",  # Missing duration
            instructions="",
            age_range="10-24 years",  # Wrong format
        ),
    ]
    
    print("=" * 60)
    print("BEFORE CORRECTION")
    print("=" * 60)
    for med in sample_medicines:
        print(f"Medicine: {med.medicine}")
        print(f"  Dose: {med.dose}")
        print(f"  Frequency: {med.frequency}")
        print(f"  Duration: {med.duration}")
        print(f"  Age Range: {med.age_range}")
        print()
    
    # Apply corrections
    print("\n" + "=" * 60)
    print("APPLYING CORRECTIONS...")
    print("=" * 60)
    
    corrected = await correct_medicines_batch(sample_medicines)
    
    print("\n" + "=" * 60)
    print("AFTER CORRECTION")
    print("=" * 60)
    for med in corrected:
        print(f"Medicine: {med.medicine}")
        print(f"  Dose: {med.dose}")
        print(f"  Frequency: {med.frequency}")
        print(f"  Duration: {med.duration}")
        print(f"  Age Range: {med.age_range}")
        print()


if __name__ == "__main__":
    asyncio.run(run_test_correction())
