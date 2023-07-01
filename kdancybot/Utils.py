from rosu_pp_py import Beatmap, Calculator
import json

PP_RECORD = 1371
DEFAULT_USER = "5199332"

Mods = {
    "NF": 1,
    "EZ": 2,
    "HT": 256,
    "HR": 16,
    "SD": 32,
    "PF": 16384,
    "DT": 64,
    "NC": 576,
    "HD": 8,
    "FL": 1024,
    "SO": 4096,
    "V2": 536870912,
}


def username_from_response(response, username=""):
    if str(username).lower() not in ["leva_russian", "peko_russian"]:
        username = response["username"]
    return username + " (#" + str(response["statistics"]["global_rank"]) + ")"


def map_name_from_response(score_data):
    # Very bad hack
    beatmap = score_data.get("beatmap", score_data)
    return f"{score_data['beatmapset']['artist']} - {score_data['beatmapset']['title']} [{beatmap['version']}]"


def pp_to_overtake(top100, user_pp, goal_pp):
    pp_value = -1
    if user_pp >= goal_pp:
        return pp_value

    pp_values = [score["pp"] for score in top100]
    weighted = [0.95**i * pp_values[i] for i in range(len(pp_values))]
    wsum = sum(weighted)
    bonus_pp = user_pp - wsum
    temp = pp_values

    # if player gets pp record and still doesn't get goal pp
    if wsum * 0.95 + bonus_pp + PP_RECORD < goal_pp:
        return pp_value

    # TODO: Rewrite loop so weighted doesn't get recalculated every cycle
    for i in range(len(temp) - 1, 0, -1):
        temp[i] = temp[i - 1]
        weighted = [0.95**j * temp[j] for j in range(len(temp))]
        wsum = sum(weighted)
        if wsum + bonus_pp > goal_pp:
            pp_value = temp[i] - (wsum + bonus_pp - goal_pp) / (0.95**i)
            break

    # if player can get goal pp only by getting personal best
    if pp_value == -1:
        pp_value = temp[0] + (goal_pp - wsum - bonus_pp)
    return pp_value


def build_calculator(score_data):
    mods = 0
    for mod in score_data["mods"]:
        mods += int(Mods[mod])
    calc = Calculator(
        mode=0,
        mods=mods,
        n300=score_data["statistics"]["count_300"],
        n100=score_data["statistics"]["count_100"],
        n50=score_data["statistics"]["count_50"],
        n_misses=score_data["statistics"]["count_miss"],
        combo=score_data["max_combo"],
    )
    return calc


def get_passed_objects(score_data):
    stats = score_data["statistics"]
    return (
        stats["count_300"]
        + stats["count_100"]
        + stats["count_50"]
        + stats["count_miss"]
    )


def get_objects_count(score_data):
    beatmap = score_data["beatmap"]
    return (
        beatmap["count_circles"] + beatmap["count_spinners"] + beatmap["count_sliders"]
    )


def generate_mods_payload(mods):
    payload = ""
    for mod in mods:
        payload += "mods%5B%5D=" + mod + "&"
    if len(payload):
        payload = payload[:-1]
    return payload