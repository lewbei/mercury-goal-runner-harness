# Certifier Golden Behavior Lock V1

## Overview

This document describes the certifier golden behavior lock.

## pre-refactor behavior lock

The certifier uses pre-refactor behavior lock to maintain compatibility.

## does not modularize `certify_run.py`

The lock does not modularize `certify_run.py`.

## P2 weak verifier evidence -> PROVISIONAL_DONE

P2 weak verifier evidence results in PROVISIONAL_DONE.

## policy says CERTIFIED_DONE but replay gate fails -> final NOT_DONE from certification.json

If policy says CERTIFIED_DONE but replay gate fails, the final status is NOT_DONE from certification.json.

## final_status.md cannot upgrade final_status.json authority

The `final_status.md` cannot upgrade `final_status.json` authority.

## bounded regression evidence

The lock uses bounded regression evidence.

## Status

Implemented and tested.
