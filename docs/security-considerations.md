# Security considerations

Uploads are bounded by `MAX_UPLOAD_BYTES`, filenames reject path traversal, input uses Pydantic validation, YAML uses `yaml.safe_load`, and no user-controlled shell command is executed. Persistence uses SQLAlchemy rather than string-concatenated SQL.

Generated Terraform is a **DRAFT starter only**. The application never calls `terraform apply`, never requests cloud credentials, and emits no provider resources automatically. The starter contains no public database or `0.0.0.0/0` administrative ingress rule.

Security output lists controls relevant to data sensitivity, RTO/RPO, identity, auditability, encryption, backup and segmentation. It never claims that an architecture is certified compliant with PCI, GDPR, SOX, or another regime.
