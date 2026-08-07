Evals
===============
.. contents:: :local:


LLM Interfaces
------------------

LLM
~~~~~~~~~~~
.. autoclass:: a2e.evals.llm.LLM
   :members:
   :show-inheritance:


Prompt Template
~~~~~~~~~~~~~~~
.. autoclass:: a2e.evals.templating.Template
   :members:
   :show-inheritance:


Evaluator Abstractions
----------------------

Evaluator Base
~~~~~~~~~~~~~~
.. autoclass:: a2e.evals.Evaluator
   :members:
   :show-inheritance:

LLMEvaluator
~~~~~~~~~~~~
.. autoclass:: a2e.evals.LLMEvaluator
   :members:
   :show-inheritance:

ClassificationEvaluator
~~~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: a2e.evals.ClassificationEvaluator
   :members:
   :show-inheritance:

Core Functions
--------------

create_evaluator
~~~~~~~~~~~~~~~~
.. autofunction:: a2e.evals.create_evaluator

create_classifier
~~~~~~~~~~~~~~~~~
.. autofunction:: a2e.evals.create_classifier


bind_evaluator
~~~~~~~~~~~~~~
.. autofunction:: a2e.evals.bind_evaluator

evaluate_dataframe
~~~~~~~~~~~~~~~~~~
.. autofunction:: a2e.evals.evaluators.evaluate_dataframe

async_evaluate_dataframe
~~~~~~~~~~~~~~~~~~~~~~~~
.. autofunction:: a2e.evals.evaluators.async_evaluate_dataframe


Score
-----

Score
~~~~~~
.. autoclass:: a2e.evals.Score
   :members:
   :exclude-members: name, score, label, explanation, metadata, kind, direction
   :show-inheritance:


Built-in Metrics
------------------

.. automodule:: a2e.evals.metrics
   :members:

Utilities
---------

.. automodule:: a2e.evals.utils
   :members:
   :exclude-members: InputMappingType, download_benchmark_dataset, emoji_guard
