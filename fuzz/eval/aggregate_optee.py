#!/usr/bin/env python
from __future__ import print_function
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))
import logging
import json

from optee_structs import OPTEEReturnStatus, OPTEEReturnStatus_dict, OPTEEReturnOrigin, OPTEEReturnOrigin_dict
from linux import IOCTL_ReturnCodes, IOCTL_ReturnCodes_dict

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__file__)

""" example for data in one of the return_codes.json files:
{
    "config": "config/tc/tc_km_11.json",
    "return_codes": {
        "TEEC_ORIGIN_NOT_SET": {
            "TEE_CODE_NOT_SET": 82
        },
        "TEEC_ORIGIN_TEE": {
            "TEEC_ERROR_BAD_PARAMETERS": 65,
            "TEEC_ERROR_GENERIC": 353
        },
        "ioctl_ret": {
            "EFAULT": 418,
            "EPERM": 82
        }
    }
}
"""

RETURN_CODES_KEY = 'return_codes'
IOCTL_RET_KEY = 'ioctl_ret'

def get_ioctl_request_count(return_data):
    """ count all ioctl return codes we collected """
    count = 0
    for return_ in return_data:
        for v in return_[RETURN_CODES_KEY][IOCTL_RET_KEY].values():
            count += v
    return count


def get_raw_request_count(return_data):
    """ count all return codes no matter what's the origin """
    count = 0
    for return_ in return_data:
        for k in return_[RETURN_CODES_KEY].keys():
            for kk in return_[RETURN_CODES_KEY][k].keys():
                count += return_[RETURN_CODES_KEY][k][kk]

    return count


def get_crash_count(return_data):
    """ count all TARGET_DEAD return statuses """
    count = 0
    for return_ in return_data:
        for k in return_[RETURN_CODES_KEY].keys():
            if OPTEEReturnStatus_dict[OPTEEReturnStatus.TEEC_ERROR_TARGET_DEAD] in return_[RETURN_CODES_KEY][k]:
                count += return_[RETURN_CODES_KEY][k][OPTEEReturnStatus_dict[OPTEEReturnStatus.TEEC_ERROR_TARGET_DEAD]]

    return count


def get_send_to_tee_count(return_data):
    """ count all return codes originating from the TEE """
    count = 0
    for return_ in return_data:
        origin_key = OPTEEReturnOrigin_dict[OPTEEReturnOrigin.TEEC_ORIGIN_TEE]
        if origin_key in return_[RETURN_CODES_KEY]:
            for v in return_[RETURN_CODES_KEY][origin_key].values():
                count += v
        origin_key = OPTEEReturnOrigin_dict[OPTEEReturnOrigin.TEEC_ORIGIN_TRUSTED_APP]
        if origin_key in return_[RETURN_CODES_KEY]:
            for v in return_[RETURN_CODES_KEY][origin_key].values():
                count += v
        """
        origin_key = OPTEEReturnOrigin_dict[OPTEEReturnOrigin.TEEC_ORIGIN_NOT_SET]
        if origin_key in return_[RETURN_CODES_KEY]:
            for v in return_[RETURN_CODES_KEY][origin_key].values():
                count += v
        """
    return count


def get_valid_smc_count(return_data):
    """ count all ioctl return codes indicating a successful request """

    valid_returns = [OPTEEReturnStatus_dict[OPTEEReturnStatus.TEEC_SUCCESS]]
    count = 0
    for return_ in return_data:
        origin_key = OPTEEReturnOrigin_dict[OPTEEReturnOrigin.TEEC_ORIGIN_TRUSTED_APP]
        if origin_key in return_[RETURN_CODES_KEY]:
            for k in return_[RETURN_CODES_KEY][origin_key].keys():
                if k in valid_returns:
                    count += return_[RETURN_CODES_KEY][origin_key][k]
        origin_key = OPTEEReturnOrigin_dict[OPTEEReturnOrigin.TEEC_ORIGIN_TEE]
        if origin_key in return_[RETURN_CODES_KEY]:
            for k in return_[RETURN_CODES_KEY][origin_key].keys():
                if k in valid_returns:
                    count += return_[RETURN_CODES_KEY][origin_key][k]

        # TODO: figure out if OPTEEReturnOrigin.TEEC_ORIGIN_API and OPTEEReturnOrigin.TEEC_ORIGIN_COMMS
        # sometimes originate from TEE too
    return count

def get_valid_ioctl_count(return_data):
    """ count all smc return codes indicating a successful request """

    valid_returns = [IOCTL_ReturnCodes_dict[IOCTL_ReturnCodes.SUCCESS]]
    count = 0
    for return_ in return_data:
        if IOCTL_RET_KEY in return_[RETURN_CODES_KEY]:
            for k in return_[RETURN_CODES_KEY][IOCTL_RET_KEY].keys():
                if k in valid_returns:
                    count += return_[RETURN_CODES_KEY][IOCTL_RET_KEY][k]
    return count


def main(dir_):
    paths = [os.path.join(dir_, path) for path in os.listdir(dir_)]

    return_data = []

    for path in paths:
        with open(path) as f:
            return_data.append(json.loads(f.read()))

    # time
    duration = 90 * 60
    log.info("duration: {}secs".format(duration))
    # raw requests / ioctls
    raw_request_count = get_raw_request_count(return_data)
    log.info("#raw_reqs: {}".format(raw_request_count))
    # throughput
    throughput = raw_request_count / duration
    log.info("{} requests per sec".format(throughput))
    # successful ioctls (ret = 0)
    valid_ioctl_count = get_valid_ioctl_count(return_data)
    log.info("#valid_ioctls: {}".format(valid_ioctl_count))
    # err ioctls (ret != 0)
    log.info("#invalid_ioctls: {}".format(raw_request_count - valid_ioctl_count))
    # sent to tee
    smc_total = get_send_to_tee_count(return_data)
    log.info("#reached_tee: {}".format(smc_total))
    # valid return
    smc_valid = get_valid_smc_count(return_data)
    log.info("#valid_smcs: {}".format(smc_valid))
    # invalid return
    log.info("#invalid_smcs: {}".format(smc_total - smc_valid))
    # crashes
    log.info("#crashes: {}".format(get_crash_count(return_data)))
    # unique crashes
    # TODO

    return


def usage():
    print("{} <return_codes_dir>".format(sys.argv[0]))
    return


if __name__=="__main__":

    if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
        usage()
        sys.exit(0)

    main(sys.argv[1])