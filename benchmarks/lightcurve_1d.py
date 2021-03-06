import numpy as np
import os
import time
import yaml
from pathlib import Path
import astropy.units as u
from astropy.coordinates import SkyCoord, Angle
from regions import CircleSkyRegion
from gammapy.maps import MapAxis
from gammapy.data import DataStore, GTI
from gammapy.modeling.models import PowerLawSpectralModel
from gammapy.spectrum import SpectrumDatasetMaker, ReflectedRegionsBackgroundMaker, SpectrumDatasetOnOff
from gammapy.cube import SafeMaskMaker
from gammapy.time import LightCurveEstimator

N_OBS = int(os.environ.get("GAMMAPY_BENCH_N_OBS", 10))


def data_prep():
    data_store = DataStore.from_dir("$GAMMAPY_DATA/hess-dl3-dr1/")
    OBS_ID = 23523
    obs_ids = OBS_ID * np.ones(N_OBS)
    observations = data_store.get_observations(obs_ids)
    
    target_position = SkyCoord(ra=83.63308, dec=22.01450, unit="deg")

    e_reco = MapAxis.from_bounds(0.1, 40, nbin=40, interp="log", unit="TeV").edges
    e_true = MapAxis.from_bounds(0.05, 100, nbin=200, interp="log", unit="TeV").edges

    on_region_radius = Angle("0.11 deg")
    on_region = CircleSkyRegion(center=target_position, radius=on_region_radius)

    dataset_maker = SpectrumDatasetMaker(
         containment_correction=True, selection=["counts", "aeff", "edisp"]
    )

    empty = SpectrumDatasetOnOff.create(region=on_region, e_reco=e_reco, e_true=e_true)

    bkg_maker = ReflectedRegionsBackgroundMaker()
    safe_mask_masker = SafeMaskMaker(methods=["aeff-max"], aeff_percent=10)

    spectral_model = PowerLawSpectralModel(
        index=2.6, amplitude=2.0e-11 * u.Unit("1 / (cm2 s TeV)"), reference=1 * u.TeV
    )
    spectral_model.index.frozen = False

    model = spectral_model.copy()
    model.name = "crab"

    datasets_1d = []

    for observation in observations:

        dataset = dataset_maker.run(dataset=empty.copy(), observation=observation)

        dataset_on_off = bkg_maker.run(dataset, observation)
        dataset_on_off = safe_mask_masker.run(dataset_on_off, observation)
        datasets_1d.append(dataset_on_off)

    for dataset in datasets_1d:
        model = spectral_model.copy()
        model.name = "crab"
        dataset.model = model

    return datasets_1d


def data_fit(datasets):
    lc_maker_1d = LightCurveEstimator(datasets, source="crab", reoptimize=False)
    lc_1d = lc_maker_1d.run(e_ref=1 * u.TeV, e_min=1.0 * u.TeV, e_max=10.0 * u.TeV)


def run_benchmark():
    info = {"n_obs": N_OBS}

    t = time.time()

    datasets = data_prep()
    info["data_preparation"] = time.time() - t
    t = time.time()

    data_fit(datasets)
    info["data_fitting"] = time.time() - t
    t = time.time()

    Path("bench.yaml").write_text(yaml.dump(info, sort_keys=False, indent=4))


if __name__ == "__main__":
    run_benchmark()
