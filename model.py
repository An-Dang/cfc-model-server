"""

IDE: PyCharm
Project: semantic-match-classifier
Author: Robin
Filename: model.py
Date: 21.03.2020

"""
import json

import torch
import torch.nn as nn
from transformers import BertForSequenceClassification, DistilBertModel


def get_config_and_device(config_file, cpu_only=False):
    # "data/config/bert_cls_config.json"
    with open(config_file, "r", encoding="utf8") as config_file:
        config = json.load(config_file)

    # init device
    device = torch.device("cuda") if torch.cuda.is_available() and not cpu_only else torch.device("cpu")
    print("Device: " + str(device))

    return config, device

def get_model(model_name, config, device):
    if model_name == "bert_cls_basic":
        return BertClassifierModel(**config).to(device)
    elif model_name == "bert_matcher_basic":
        return BertMatcherModel(**config).to(device)
    raise Exception("Unknown model %s" % model_name)

def squeeze_tensors(tensors, dim=1):
    return [tensor.squeeze(dim=dim) for tensor in tensors]

def copy_to_device(tensors, columns, device):
    data = dict()
    for i in range(len(columns)):
        column = columns[i]
        data[column] = tensors[i].squeeze(dim=1).to(device)
    return data

class BertMatcherModel(nn.Module):
    def __init__(self, n_classes=3, dropout=0.1, max_sequence_length=50):
        """
        Matcher Modell
        :param n_outputs:
        """
        super(BertMatcherModel, self).__init__()

        self.dropout = nn.Dropout(dropout)

        self.max_sequence_length = max_sequence_length
        self.distilbert_hidden_dim = 768
        self.matched_dim = 4096

        self.matcher = nn.Linear(in_features=2 * self.distilbert_hidden_dim * max_sequence_length,
                                 out_features=self.matched_dim)
        self.predictor = nn.Linear(in_features=self.matched_dim, out_features=n_classes)

        self.distilbert_model = DistilBertModel.from_pretrained("distilbert-base-german-cased", force_download=False, proxies={},
                                                                cache_dir="/cache")

    def forward(self, token_id_tensor_a, attn_mask_tensor_a, token_id_tensor_b, attn_mask_tensor_b, **kwargs):
        tensors_a = [token_id_tensor_a, attn_mask_tensor_a]
        tensors_b = [token_id_tensor_b, attn_mask_tensor_b]

        # encoder and get last hidden states
        hidden_a = self.distilbert_model(input_ids=tensors_a[0], attention_mask=tensors_a[1])[0]
        hidden_b = self.distilbert_model(input_ids=tensors_b[0], attention_mask=tensors_b[1])[0]

        # concate all states
        concat_a_b = torch.cat((hidden_a, hidden_b), dim=1)
        combined = concat_a_b.view(concat_a_b.size(0), concat_a_b.size(1) * concat_a_b.size(2))

        # match and predict
        matched_a_b = self.matcher(self.dropout(combined))
        predicted_a_b = self.predictor(matched_a_b)

        return predicted_a_b

class BertClassifierModel(nn.Module):
    def __init__(self, n_classes=3, dropout=0.2, max_sequence_length=100):
        """
        Simple classifier model: BERT + Linear on top of pooled output last layer
        :param n_classes:
        """
        super(BertClassifierModel, self).__init__()
        self.bert_model = BertForSequenceClassification.from_pretrained("bert-base-german-cased", num_labels=n_classes, force_download=False, proxies={},
                                                                        cache_dir="/cache", hidden_dropout_prob=dropout)

    def forward(self, token_id_tensor, type_id_tensor, attn_mask_tensor, **kwargs):
        return self.bert_model(input_ids=token_id_tensor, token_type_ids=type_id_tensor, attention_mask=attn_mask_tensor)[0]
