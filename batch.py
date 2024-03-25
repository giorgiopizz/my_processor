import json
import subprocess
import cloudpickle
import zlib
import os
from math import ceil

if __name__ == "__main__":
    with open("data/chunks.json", "r") as file:
        chunks = json.load(file)

    maxfiles = 100000
    # for dataset in chunks:
    new_chunks = []
    # for dataset in ["DY", 'Zjj', 'Double']:
    for dataset in ["DY", "SingleMuon", "DoubleMuon", "MuonEG"]:
        meta = chunks[dataset]["metadata"]
        ifile = 0
        for file in chunks[dataset]["files"]:
            for step in chunks[dataset]["files"][file]["steps"]:
                print(step)
                start, stop = step
                # result = big_process(file, start, stop, dataset=dataset, **meta)
                new_chunks.append(
                    dict(filename=file, start=start, stop=stop, dataset=dataset, **meta)
                )
                # break
            ifile += 1
            if ifile >= maxfiles:
                break

    print("N chunks", len(new_chunks))
    # maxjobs = 200
    # chunks_per_job = ceil(len(new_chunks)/maxjobs)
    chunks_per_job = 10
    njobs = ceil(len(new_chunks) / chunks_per_job)
    print("Chunks per job", chunks_per_job)
    print("Number of jobs", njobs)
    jobs = []
    for i in range(njobs):
        start = i * chunks_per_job
        stop = min((i + 1) * chunks_per_job, len(new_chunks))
        if start >= stop:
            break
        print(start, stop)
        jobs.append(new_chunks[start:stop])

    print(len(jobs))

    folders = []
    path = os.path.abspath(".")

    proc = subprocess.Popen("rm -r condor; rm -r results", shell=True)
    proc.wait()

    for i, job in enumerate(jobs):
        folder = f"condor/job_{i}"
        proc = subprocess.Popen(
            f"mkdir -p {folder}; ",
            shell=True,
        )
        proc.wait()

        with open(f"{folder}/chunks_job.pkl", "wb") as file:
            file.write(zlib.compress(cloudpickle.dumps(job)))

        folders.append(folder.split("/")[-1])

    proc = subprocess.Popen("cp script_worker.py condor/", shell=True)
    proc.wait()

    txtsh = "#!/bin/bash\n"
    txtsh += "export X509_USER_PROXY=/gwpool/users/gpizzati/.proxy\n"

    txtsh += "source /gwpool/users/gpizzati/mambaforge/etc/profile.d/conda.sh\n"
    txtsh += "source /gwpool/users/gpizzati/mambaforge/etc/profile.d/mamba.sh\n"
    txtsh += "mamba activate test_uproot\n"

    txtsh += f"export PYTHONPATH={path}:$PYTHONPATH\n"
    txtsh += "echo 'which python'\n"
    txtsh += "which python\n"
    txtsh += "time python script_worker.py\n"
    txtsh += f"cp results.pkl {path}/results/results_${1}.pkl\n"
    print(txtsh)
    with open("condor/run.sh", "w") as file:
        file.write(txtsh)

    txtjdl = "universe=vanilla\n"
    txtjdl = "universe = vanilla \n"
    txtjdl += "executable = run.sh\n"
    txtjdl += "arguments = $(Folder)\n"

    txtjdl += "should_transfer_files = YES\n"
    txtjdl += "transfer_input_files = $(Folder)/chunks_job.pkl, script_worker.py, ../data/cfg.json\n"
    txtjdl += "output = $(Folder)/out.txt\n"
    txtjdl += "error  = $(Folder)/err.txt\n"
    txtjdl += "log    = $(Folder)/log.txt\n"
    txtjdl += "request_cpus=1\n"
    queue = "workday"
    txtjdl += f'+JobFlavour = "{queue}"\n'

    txtjdl += f'queue 1 Folder in {", ".join(folders)}\n'
    with open("condor/submit.jdl", "w") as file:
        file.write(txtjdl)

    proc = subprocess.Popen(
        "mkdir -p results; cd condor/; condor_submit submit.jdl; cd -", shell=True
    )
    proc.wait()