# Installation
We introduce how to install optinist.
We have developed optinist python(backend) and typescript(frontend), so you need to make both environment.
Please follow instrunctions below.

<br />

# 1. Clone optinist repository

First, you get optinist code from github repository.
```
cd "your working repository"
git clone git@github.com:oist/optinist.git
```

If you don't have access authority, please contact with a person who is in charge.

<br />

# 2. Make frontend environment
** For windows users or others who doesn't want to install docker users.
When docker installation is sometimes wrong, it's easy to install nodejs directly and launch frontend in nodejs.

- How to install nodejs
https://nodejs.org/ja/download/
- launch command
```
cd optinist/frontend
yarn start
```

open `localhost:3000`  
and skip install docker document.  
**


## Install docker

Install docker from docker site. [https://docs.docker.com/get-docker/]

**** If you get memory error, increase memory to use. ****

Launching docker and increase memory capacity.

How to open setting display.
- [For Windows](https://docs.docker.com/desktop/windows/)
- [For Mac](https://docs.docker.com/desktop/mac/)
- [For Linux](https://docs.docker.com/desktop/linux/)

**** memory setting ****

Please, Check whether docker is open or not in the command.
```
docker ps
```

If you get the message below, docker has not been launched. In that case, click docker icon in your LaunchPad(mac).

> Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?


## docker build
check your working repository in `optinist`.
```
cd optinist
```

Build frontend code.
```
docker-compose build frontend
```

## docker up
Launch frontend.
```
docker-compose up frontend
```

Launch browser.  http://localhost:3000  
It opens correctly!

<br />

# 3. make backend environment

## Create anaconda environment
optinist support anaconda.

[anaconda install from this page](https://www.anaconda.com/products/individual)


We introduce how to setup in anaconda environment.

Create conda environment, named `optinist`
```
conda create -n optinist python=3.8
conda activate optinist
```

FAQ
If you have get below warning, I recommend `rm -rf /Users/usename/opt/anaconda3/envs/optinist ` and recreate conda environment.
> WARNING: A directory already exists at the target location '/Users/usename/opt/anaconda3/envs/optinist' but it is not a conda environment.

## Install mamba
We use snakemake library, it needs mamba.
```
conda install -n base -c conda-forge mamba
```

<br />

## Install library
Check you're working directory in `optinist/backend`.
```
cd optinist/backend
```

Install library from requirements.txt
```
pip install -r requirements.txt
```
<br />

## Install caiman
- For m1 mac user  
We use tensorflow in caiman code. We know that M1 mac doesn't install tensorflow easily, so if there is a proboem, skip install caiman. (Release in progress…)

** If you use m1 mac, skip this.  

Check you're working in `optinist` environment.
```
conda activate optinist
```

Install other library for using caiman
```
pip install cython opencv-python matplotlib scikit-image==0.18.0 scikit-learn ipyparallel holoviews watershed tensorflow
```

Install caiman, donwload directory is up to you.
```
git clone https://github.com/flatironinstitute/CaImAn -b v1.9.7
cd /CaImAn && pip install -e .
```

<br />

## Check library
* You can check install library from ```pip list``` command.
* If you install numpy after install caiman, you get numpy error. Because of numpy and Cython version conflict. 
[https://stackoverflow.com/questions/66060487/valueerror-numpy-ndarray-size-changed-may-indicate-binary-incompatibility-exp]

## Run backend
Check you're working directory in `optinist/backend`
```
cd optinist/backend
```

run backend
```
python main.py
```

It opens correctly!