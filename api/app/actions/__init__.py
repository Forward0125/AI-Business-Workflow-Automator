"""Mocked CRM / calendar / email actions.

The pipeline's last three steps (crm / calendar / email) write rows
to the ``mocked_actions`` table with believable JSON payloads, but
do NOT call any real SaaS. The honest-demo philosophy: AI parts
real, integration parts simulated.
"""
