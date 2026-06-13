-- SQL schema for the Django PresidentProfile table.
-- Use this in SQLYOG after the Django auth tables already exist.

CREATE TABLE `website_presidentprofile` (
  `id` int NOT NULL AUTO_INCREMENT,
  `role` varchar(64) NOT NULL,
  `created_at` datetime NOT NULL,
  `created_by_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `website_presidentprofile_user_id_key` (`user_id`),
  KEY `website_presidentprofile_created_by_id_idx` (`created_by_id`),
  CONSTRAINT `website_presidentprofile_created_by_id_fk` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `website_presidentprofile_user_id_fk` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
