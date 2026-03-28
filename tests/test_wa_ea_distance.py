import subprocess
import sys


def test_smoke_wa_ea_script_runs(tmp_path):
    # Minimal smoke test: create small sample WA/EA files and run the script module
    wa = tmp_path / "wa.txt"
    ea = tmp_path / "ea.txt"
    wa.write_text("Սա լավ տուն է։", encoding="utf-8")
    ea.write_text("Սա լավ տուն է։", encoding="utf-8")

    outdir = tmp_path / "out"
    outdir.mkdir()

    cmd = [sys.executable, "scripts/wa_ea_distance.py", "--wa", str(wa), "--ea", str(ea), "--outdir", str(outdir)]
    proc = subprocess.run(cmd, check=False)
    assert proc.returncode == 0, f"Script failed with exit code {proc.returncode}"


def test_orthography_converter():
    from hytools.linguistics.orthography.reform_classical_converter import to_reformed, to_classical, orthography_score

    sample = "գիւղ իւր իւղ երկրաւ"
    reformed = to_reformed(sample)
    assert isinstance(reformed, str)
    classical = to_classical(reformed)
    assert isinstance(classical, str)
    score = orthography_score(sample)
    assert 0.0 <= score <= 1.0
