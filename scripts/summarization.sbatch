#!/bin/bash
#SBATCH --job-name=mirdata-summarize
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --mem=32GB
#SBATCH --gres=gpu:1
#SBATCH --output=/scratch/yd3245/projects/mirdata-gallery/mirdata-gallery/logs/summarize_%j.out
#SBATCH --error=/scratch/yd3245/projects/mirdata-gallery/mirdata-gallery/logs/summarize_%j.err
#SBATCH --account=torch_pr_1003_general

# Ensure output directories exist
mkdir -p /scratch/yd3245/projects/mirdata-gallery/mirdata-gallery/logs

singularity exec --nv \
    --overlay /scratch/yd3245/images/overlay-25GB-500K.ext3:ro \
    /share/apps/images/cuda11.8.86-cudnn8.7-devel-ubuntu22.04.2.sif \
    /bin/bash -c "

        export PYTHONNOUSERSITE=1
        cd /scratch/yd3245/projects/mirdata-gallery/mirdata-gallery
        /scratch/yd3245/envs/conda_envs/my_env/bin/python utils/summarize_datasets_llm.py --model Qwen/Qwen2.5-7B-Instruct
    "