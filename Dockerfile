FROM python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36
ENV MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 PYTHONWARNINGS=ignore PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /opt/requirements.txt
RUN pip install --no-cache-dir setuptools==80.10.2 wheel && pip install --no-cache-dir --no-build-isolation -r /opt/requirements.txt
COPY requirements-lock.txt /opt/requirements-lock.txt
RUN pip install --no-cache-dir --no-build-isolation -r /opt/requirements-lock.txt
RUN useradd --uid 1000 --create-home agent && mkdir -p /opt/gri_bench /task /work/output && chown -R agent:agent /work
RUN ln -s /work/instance.json /task/instance.json
COPY src/gri_bench/__init__.py src/gri_bench/api.py src/gri_bench/physiology.py src/gri_bench/release.py src/gri_bench/native.py /opt/gri_bench/
RUN printf '/opt\n' > /usr/local/lib/python3.12/site-packages/gri_bench.pth
COPY docs/AGENT_TASK.md /task/README.md
# Warm identical Numba code before timed trials. No instance or seed file is copied.
ENV NUMBA_CACHE_DIR=/tmp/numba MPLCONFIGDIR=/tmp/matplotlib
RUN python -c 'from gri_bench.physiology import *; p,x=patient_parameters("adult#001"); fast_trace(p,x,np.zeros(6),np.array([0.,1.,150.,2.,10.,100.]))' && cp -R /tmp/numba /opt/numba-cache && chmod -R a+rX /opt
WORKDIR /work
USER agent
CMD ["sleep", "infinity"]
