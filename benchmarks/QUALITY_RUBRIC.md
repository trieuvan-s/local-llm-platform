# A/B quality rubric

Score each category from 0 to 5. Throughput is reported separately and never substitutes for quality.

## Coding

1. Complete, syntactically coherent implementation.
2. No look-ahead; exactly `window` observations are required.
3. A window containing `None` produces `None`.
4. Population standard deviation and zero-variance behavior match the task.
5. Exactly six meaningful tests with correct numeric expectations; complexity is stated accurately.

Do not execute generated model code on the host. Review it as untrusted output.

## Financial data analysis

1. Revenue QoQ: 20.0%, 25.0%; net-income QoQ: 37.5%, about 36.4%.
2. Net margins: 8.0%, about 9.17%, 10.0%.
3. CFO/net income: 25.0%, about -27.27%, -40.0%.
4. Receivables/assets is computed only for Q3: about 34.44%; Q1/Q2 are explicitly unavailable.
5. Flags two consecutive negative-CFO quarters against positive/increasing profit and rapidly increasing receivables, without treating mock data as a real company.
