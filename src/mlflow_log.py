from typing import Dict
import mlflow
import tensorflow
import os
import numpy as np

class MLFlowLogger:
    def __init__(self, config: Dict):
        mlflow.set_tracking_uri(config["logging"]["tracking_url"])
        experiment_id = mlflow.set_experiment(experiment_name=config["data"]["dataset_name"])
        mlflow.start_run(experiment_id=experiment_id, run_name=config["logging"]["run_name"])
        self.config = config

    def config_logging(self):
        mlflow.log_params(self.config['model'])
        mlflow.log_params(self.config['model']['feature_extractor'])
        mlflow.log_params(self.config['data'])
        head_type = self.config['model']['head']['type']
        mlflow.log_param('head_type', head_type)
        mlflow.log_params(self.config['model']['head'][head_type])

    def test_logging(self, metrics: Dict):
        mlflow.log_metrics(metrics)


class MLFlowCallback(tensorflow.keras.callbacks.Callback):
    def __init__(self, config):
        super().__init__()
        self.finished_epochs = 0
        self.best_result = 0.0
        self.config = config

    def on_batch_end(self, batch: int, logs=None):
        if batch % 100 == 0:
            current_step = (self.finished_epochs * self.params['steps']) + batch
            metrics_dict = self._format_metrics_for_mlflow(logs)
            mlflow.log_metrics(metrics_dict)

    def on_epoch_end(self, epoch: int, logs=None):
        self.finished_epochs = epoch + 1
        current_step = self.finished_epochs * self.params['steps']

        metrics_dict = self._format_metrics_for_mlflow(logs)
        mlflow.log_metrics(metrics_dict, step=current_step)
        mlflow.log_metric('finished_epochs', self.finished_epochs, step=current_step)

        # Check if new best model
        if metrics_dict["val_f1_mean"] > self.best_result:
            print("\n New best model! Saving model..")
            self.best_result = metrics_dict["val_f1_mean"]
            if self.config["model"]["save_name"] != "None":
                self._save_model()
            mlflow.log_metric("best_val_f1_mean", metrics_dict["val_f1_mean"])
            mlflow.log_metric("saved_model_epoch", self.finished_epochs)

    def _format_metrics_for_mlflow(self, logs):
        mlflow_dict = logs.copy()
        f1_score = mlflow_dict.pop('f1_score')
        mlflow_dict['f1_mean'] = np.mean(f1_score)
        if 'val_f1_score' in mlflow_dict.keys():
            f1_score = mlflow_dict.pop('val_f1_score')
            mlflow_dict['val_f1_mean'] = np.mean(f1_score)

        return mlflow_dict

    # TODO: fix save bug for gp and bnn head
    def _save_model(self):
        save_dir = os.path.join(self.config["data"]["artifact_dir"], "models")
        name = self.config["model"]["save_name"]
        os.makedirs(save_dir, exist_ok=True)
        fe_path = os.path.join(save_dir, name + "_feature_extractor.h5")
        head_path = os.path.join(save_dir, name + "_head.h5")
        self.model.layers[0].save_weights(fe_path)
        self.model.layers[1].save_weights(head_path)
