# %%
import shutil
from pathlib import Path

import numpy as np
import torch

from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
# from lerobot.common.datasets.lerobot_dataset import LEROBOT_HOME, LeRobotDataset
# from lerobot.common.datasets.push_dataset_to_hub._download_raw import download_raw

PUSHT_TASK = "Push the T-shaped blue block onto the T-shaped green target surface with a scara."
PUSHT_FEATURES = {
    "observation.state": {
        "dtype": "float32",
        "shape": (3,),
        "names": {
            "axes": ["x", "y", "z"],
        },
    },
    "action": {
        "dtype": "float32",
        "shape": (3,),
        "names": {
            "axes": ["x", "y", "z"],
        },
    },
    # "timestamp": {
    #     "dtype": "float32",
    #     "shape": (1,),
    #     "names": None,
    # },
    # "task": {
    #     "dtype": "string",
    #     "shape": (1,),
    #     "names": None,
    # },
    # "next.reward": {
    #     "dtype": "float32",
    #     "shape": (1,),
    #     "names": None,
    # },
    # "next.success": {
    #     "dtype": "bool",
    #     "shape": (1,),
    #     "names": None,
    # },
    # "observation.environment_state": {
    #     "dtype": "float32",
    #     "shape": (16,),
    #     "names": [
    #         "keypoints",
    #     ],
    # },
    "observation.image": {
        "dtype": None,
        "shape": (240, 320, 3),
        "names": [
            "height",
            "width",
            "channel",
        ],
    },
}
# %%

def build_features(mode: str) -> dict:
    features = PUSHT_FEATURES
    if mode == "keypoints":
        features.pop("observation.image")
    else:
        # features.pop("observation.environment_state")
        features["observation.image"]["dtype"] = mode

    return features



def load_raw_dataset(zarr_path: Path):
    try:
        # from lerobot.common.datasets.push_dataset_to_hub._diffusion_policy_replay_buffer import (
        #     ReplayBuffer as DiffusionPolicyReplayBuffer,
        # )
        from lerobot.common.datasets.replay_buffer import ReplayBuffer as DiffusionPolicyReplayBuffer
    except ModuleNotFoundError as e:
        print("`gym_pusht` is not installed. Please install it with `pip install 'lerobot[gym_pusht]'`")
        raise e

    zarr_data = DiffusionPolicyReplayBuffer.copy_from_path(zarr_path)
    return zarr_data
# %%

def main(raw_dir: Path, repo_id: str, mode: str = "image", push_to_hub: bool = False):
    if mode not in ["video", "image", "keypoints"]:
        raise ValueError(mode)

    zarr_data = load_raw_dataset(zarr_path=raw_dir / "scara-push-v0-render-v0.zarr")

    # env_state = zarr_data["state"][:]
    # agent_pos = env_state[:, :2]
    agent_pos = zarr_data["robot_eef_pos"][:]
    action = zarr_data["action"][:]
    # image = zarr_data["img"]  # (b, h, w, c)
    image = zarr_data["camera_1"]  # (b, h, w, c)

    episode_data_index = {
        "from": np.concatenate(([0], zarr_data.meta["episode_ends"][:-1])),
        "to": zarr_data.meta["episode_ends"],
    }

    features = build_features(mode)
    dataset = LeRobotDataset.create(
        repo_id=repo_id,
        root=Path("../data/datasets/scara_pusht"),
        fps=10,
        robot_type="planar eef",
        features=features,
        image_writer_threads=4,
    )
    episodes = range(len(episode_data_index["from"]))
    for ep_idx in episodes:
        from_idx = episode_data_index["from"][ep_idx]
        to_idx = episode_data_index["to"][ep_idx]
        num_frames = to_idx - from_idx

        for frame_idx in range(num_frames):
            i = from_idx + frame_idx
            frame = {
                "action": torch.from_numpy(action[i]),
                # "timestamp": torch.from_numpy(np.array([i], dtype=np.float32)),
                # "timestamp": torch.tensor(i, dtype=torch.float32),
                "task": PUSHT_TASK,
                # Shift reward and success by +1 until the last item of the episode
                # "next.reward": reward[i + (frame_idx < num_frames - 1)],
                # "next.success": success[i + (frame_idx < num_frames - 1)],
            }

            frame["observation.state"] = torch.from_numpy(agent_pos[i])

            if mode == "keypoints":
                frame["observation.environment_state"] = torch.from_numpy(keypoints[i])
            else:
                frame["observation.image"] = torch.from_numpy(image[i])

            dataset.add_frame(frame)

        dataset.save_episode()

    # dataset.consolidate()

    if push_to_hub:
        # dataset.push_to_hub()
        pass


if __name__ == "__main__":
    # To try this script, modify the repo id with your own HuggingFace user (e.g cadene/pusht)
    raw_dir = Path("../data/datasets/").resolve()
    repo_id = "scara_pusht"
    modes = ["image"]
    push_to_hub = False

    # modes = ["video", "image", "keypoints"]
    # Uncomment if you want to try with a specific mode
    # modes = ["video"]
    # modes = ["image"]
    # modes = ["keypoints"]

    # raw_dir = Path("data/lerobot-raw/pusht_raw")
    for mode in modes:
        if mode in ["image", "keypoints"]:
            repo_id += f"_{mode}"

        # download and load raw dataset, create LeRobotDataset, populate it, push to hub
        main(raw_dir, repo_id=repo_id, mode=mode)

        # Uncomment if you want to load the local dataset and explore it
        # dataset = LeRobotDataset(repo_id=repo_id, local_files_only=True)
        # breakpoint()