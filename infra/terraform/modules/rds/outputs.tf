output "cluster_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

output "db_name" {
  value = aws_rds_cluster.main.database_name
}

output "db_username" {
  value = aws_rds_cluster.main.master_username
}
