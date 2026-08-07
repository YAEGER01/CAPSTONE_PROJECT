/*
SQLyog Ultimate v13.1.1 (64 bit)
MySQL - 12.0.2-MariaDB : Database - capstone_project_db
*********************************************************************
*/

/*!40101 SET NAMES utf8 */;

/*!40101 SET SQL_MODE=''*/;

/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/`capstone_project_db` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;

USE `capstone_project_db`;

/*Table structure for table `access_session` */

DROP TABLE IF EXISTS `access_session`;

CREATE TABLE `access_session` (
  `session_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `token_id` varchar(255) NOT NULL,
  `ip_address` char(39) NOT NULL,
  `device_info` varchar(255) DEFAULT NULL,
  `issued_at` datetime(6) NOT NULL,
  `expires_at` datetime(6) NOT NULL,
  `revoked_at` datetime(6) DEFAULT NULL,
  `session_status` varchar(50) NOT NULL,
  `user_id_FK` int(11) NOT NULL,
  `last_verified_location` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`last_verified_location`)),
  `session_policy` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`session_policy`)),
  `trusted_device` tinyint(1) NOT NULL,
  `last_activity_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`session_id_PK`),
  UNIQUE KEY `token_id` (`token_id`),
  KEY `ACCESS_SESSION_user_id_FK_525a0de2_fk_OFFICER_USER_user_id_PK` (`user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=88 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `access_session` */

insert  into `access_session`(`session_id_PK`,`token_id`,`ip_address`,`device_info`,`issued_at`,`expires_at`,`revoked_at`,`session_status`,`user_id_FK`,`last_verified_location`,`session_policy`,`trusted_device`,`last_activity_at`) values 
(40,'-bbAqmiWG3IPBFD2Pl614bL6YOt6rrKfvsRSeS5rVog','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 02:57:28.432540','2026-08-07 03:42:32.404031','2026-08-07 03:42:32.404031','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T02:57:28.437984+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 02:57:28.432540'),
(41,'uAPyljvMdVgAVy-pIDWwFDaTAI18FxFphPkh7sbVgjE','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 03:00:20.576186','2026-08-07 03:44:03.222884','2026-08-07 03:44:03.222884','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T03:00:20.583687+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 03:00:20.575178'),
(42,'c7DH3gvamXvIEJ44MWDg-0vujyi63nJtPZX5yFYmU9c','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 03:00:58.624946','2026-08-07 03:45:18.460811','2026-08-07 03:45:18.460811','Revoked',49,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T03:00:58.630667+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 03:00:58.624946'),
(43,'BaNhWHKSWvotGT59UWfUo-yrqHU8B8aB7d3E7kZ_Vto','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','2026-08-07 03:03:59.665226','2026-08-07 11:03:59.665226',NULL,'Active',89,NULL,'{}',0,'2026-08-07 03:03:59.665226'),
(44,'XJRglXlxBcmaGl0ZJUMN4_NRrshn_jw6ershin7fagU','2405:8d40:4804:6e0c:557e:51d6:acfd:ea6c','Mozilla/5.0 (iPad; CPU OS 16_7_16 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/20H392 [FBAN/FBIOS;FBAV/573.0.0.22.108;FBBV/1031981006;FBDV/iPad6,7;FBMD/iPad;FBSN/iPadOS;FBSV/16.7.16;FBSS/2;FBCR/;FBID/tablet;FBLC/en_PH;FBOP/80]','2026-08-07 03:05:49.450318','2026-08-07 11:05:49.450318',NULL,'Active',88,NULL,'{}',0,'2026-08-07 03:05:49.450318'),
(45,'LW7ysl03GX3J3Z_CHaneZl6dmPsYCiMUO0N0jr0XJaA','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','2026-08-07 03:18:19.923044','2026-08-07 03:40:10.650139','2026-08-07 03:40:10.650139','Revoked',91,NULL,'{}',0,'2026-08-07 03:18:19.923044'),
(46,'z6CHWEduVfztOvrRUDmPJx_SHhQxzNi_WduDGbFnWYU','192.168.1.4','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','2026-08-07 03:18:22.281365','2026-08-07 03:55:37.317843','2026-08-07 03:55:37.317843','Revoked',93,NULL,'{}',0,'2026-08-07 03:18:22.281365'),
(47,'kOLvv_fncTDM7WnEulmrVklcqCdrmtfoudZbjZNOiEc','2405:8d40:4804:6e0c:557e:51d6:acfd:ea6c','Mozilla/5.0 (iPad; CPU OS 16_7_16 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/20H392 [FBAN/FBIOS;FBAV/573.0.0.22.108;FBBV/1031981006;FBDV/iPad6,7;FBMD/iPad;FBSN/iPadOS;FBSV/16.7.16;FBSS/2;FBCR/;FBID/tablet;FBLC/en_PH;FBOP/80]','2026-08-07 03:20:34.590175','2026-08-07 05:42:27.418401','2026-08-07 05:42:27.418401','Revoked',92,NULL,'{}',0,'2026-08-07 03:20:34.590175'),
(48,'FCEFohs2WW-P5F2wKo8xH8JadEbMIDz_UPlB_NDz8yE','111.90.232.145','Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Edg/151.0.0.0 Mobile Safari/537.36','2026-08-07 03:40:10.650139','2026-08-07 11:40:10.650139','2026-08-07 03:42:54.860376','Revoked',91,NULL,'{}',0,'2026-08-07 03:40:10.650139'),
(49,'GanGgmYPiBs38TqxQQXmhcwoLayrY-t5s-OZVP3RWUs','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 03:42:32.405190','2026-08-07 04:57:33.182753','2026-08-07 04:57:33.182753','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T03:42:32.413352+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 03:42:32.405190'),
(50,'FNhDlsUCxToSySt92XI4CJwJKzvIH6WisOVVAP15Co0','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','2026-08-07 03:43:00.136413','2026-08-07 05:09:26.689847','2026-08-07 05:09:26.689847','Revoked',91,NULL,'{}',0,'2026-08-07 03:43:00.136413'),
(51,'WafLwnxxqkDF4WrFMR3kWGD4thFJJ3bVZi_xgNk0fBk','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 03:44:03.222884','2026-08-07 04:41:59.076424','2026-08-07 04:41:59.076424','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T03:44:03.230397+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 03:44:03.222884'),
(52,'t-XIsTVrjAt-wCMuJzXG1JJCPPFkNLX1111JSQA1Q0Y','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 03:45:18.460811','2026-08-07 05:44:38.711375','2026-08-07 05:44:38.711375','Revoked',49,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T03:45:18.468643+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 03:45:18.460811'),
(53,'nmK0eqc0lTCsG00xqbsQNHsypGxJnsILmsvwwnfWDF8','192.168.1.4','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','2026-08-07 03:55:37.318849','2026-08-07 04:58:45.639946','2026-08-07 04:58:45.639946','Revoked',93,NULL,'{}',0,'2026-08-07 03:55:37.318849'),
(54,'BCjHA198DboEcG8uhCDRNToAiOQIvfqpI9IIYtBH340','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 04:41:59.084094','2026-08-07 05:14:45.413808','2026-08-07 05:14:45.413808','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T04:41:59.103665+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 04:41:59.084094'),
(55,'voZKNQ0Gm6hlNNbtFVytEA5Fpn0t6qH7UUtLDCJabz0','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 04:57:33.186369','2026-08-07 05:08:02.674939','2026-08-07 05:08:02.674939','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T04:57:33.194080+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 04:57:33.186369'),
(56,'FGxAmR3erl6x9eUXFoH0fm4FMy5Aks-IJB8SI0wGYi0','112.202.44.41','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','2026-08-07 04:58:45.639946','2026-08-07 05:04:04.579069','2026-08-07 05:04:04.579069','Revoked',93,NULL,'{}',0,'2026-08-07 04:58:45.639946'),
(57,'VSOrw31lGC1odLm38IN-LP6PoNtO86fnbj12s8Pg33g','112.202.44.41','Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Edg/151.0.0.0 Mobile Safari/537.36','2026-08-07 05:04:04.595993','2026-08-07 05:48:39.650493','2026-08-07 05:48:39.650493','Revoked',93,NULL,'{}',0,'2026-08-07 05:04:04.590078'),
(58,'Zh6WC9U61VwYTuiIBTewQTQjO10e4LaBJ-V-r3TZqTA','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 05:08:02.680731','2026-08-07 05:44:09.060596','2026-08-07 05:44:09.060596','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T05:08:02.685868+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 05:08:02.678111'),
(59,'7uoaGUPOGgG5M170gdiWg17N5rHqQL4jhI-gcVjgeh8','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','2026-08-07 05:09:26.698432','2026-08-07 05:42:12.629332','2026-08-07 05:42:12.629332','Revoked',91,NULL,'{}',0,'2026-08-07 05:09:26.698432'),
(60,'k4IUWLRXmxQr5CDeY273OI0HqeiZ55tOyZW4WVQ2Ep0','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 05:14:45.417877','2026-08-07 05:48:28.522829','2026-08-07 05:48:28.522829','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T05:14:45.427844+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 05:14:45.416809'),
(61,'cqumx5WGX6y8cDoBAY0xxWPprsYxnssMhVSRceYOHQU','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','2026-08-07 05:42:12.629332','2026-08-07 13:42:12.629332',NULL,'Active',91,NULL,'{}',0,'2026-08-07 05:42:12.629332'),
(62,'LDuzaTDHYMld1NmVlK_krdYTbDkIXPCaEbIcD-0cXTk','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36','2026-08-07 05:42:27.424459','2026-08-07 05:59:30.352238','2026-08-07 05:59:30.352238','Revoked',92,NULL,'{}',0,'2026-08-07 05:42:27.418401'),
(63,'-2r_34TkzUd6U8aV19w9k0zWIhlYI0h_m5MD03p3-SA','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 05:44:09.068142','2026-08-07 07:30:37.345304','2026-08-07 07:30:37.345304','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T05:44:09.078448+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 05:44:09.060596'),
(64,'t1HC_Bh8rQ-L2BlGxOdTSvKJxSS2oZrNi_cbfr9bSdI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 05:44:38.713666','2026-08-07 07:32:16.453713','2026-08-07 07:32:16.453713','Revoked',49,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T05:44:38.719277+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 05:44:38.713666'),
(65,'KZE393tUySMwQZm4iw2qE3cjvP3AWLjutwkaxv8_8Zw','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 05:48:28.525967','2026-08-07 06:44:02.185889','2026-08-07 06:44:02.185889','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T05:48:28.533750+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 05:48:28.525967'),
(66,'rJ8jFcDKuxeBLJijW5WETOAdsuikFSaASjF8thIQkOM','112.202.44.41','Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1','2026-08-07 05:48:39.652501','2026-08-07 07:37:38.794601','2026-08-07 07:37:38.794601','Revoked',93,NULL,'{}',0,'2026-08-07 05:48:39.652501'),
(67,'ccw0JSzzfuTEXL885ViOKihJVIj_K_A0cb8iIEh8qsg','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36','2026-08-07 05:59:30.354969','2026-08-07 07:34:30.679163','2026-08-07 07:34:30.679163','Revoked',92,NULL,'{}',0,'2026-08-07 05:59:30.354969'),
(68,'3-pYZRkdSzT6vzyn4830YFz-kogh3Dlu3J6FenIM4iQ','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 06:44:02.188424','2026-08-07 07:59:47.684070','2026-08-07 07:59:47.684070','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T06:44:02.199689+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 06:44:02.188424'),
(69,'SiGv2f0_KcUAnXzw5R_N-PszQ2Cj3zxIVzXjKoKrbtI','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 07:30:37.350597','2026-08-07 08:01:23.730064','2026-08-07 08:01:23.730064','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T07:30:37.355255+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 07:30:37.350597'),
(70,'9DwN9PwOeZLWoynqXjegLCpZuqdaZUaCBDIujtsqUdY','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 07:32:16.456463','2026-08-07 08:06:04.982496','2026-08-07 08:06:04.982496','Revoked',49,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T07:32:16.460942+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 07:32:16.455445'),
(71,'5Y4rL1w63bOlCoa9gCABmWIbaE0DmkF7bADCojPxJUI','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36','2026-08-07 07:34:30.691984','2026-08-07 15:34:30.691400',NULL,'Active',92,NULL,'{}',0,'2026-08-07 07:34:30.691400'),
(72,'SLb5OBLFh6Moy1QsCgSVn53kGuisdy6Y-R-CDiK0oDc','112.202.44.41','Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1','2026-08-07 07:37:38.801224','2026-08-07 15:37:38.801224',NULL,'Active',93,NULL,'{}',0,'2026-08-07 07:37:38.801224'),
(73,'oWvQG6C3ak4dTYRR0Izx-mTW1v1D6QOk1fzs0vTf9Xk','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 07:59:47.688190','2026-08-07 08:32:02.748633','2026-08-07 08:32:02.748633','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T07:59:47.695248+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 07:59:47.688190'),
(74,'-1Xk1Rs-EpFPZU4DjBX4b-O_RhckcM37wQiFUQzo52A','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 08:01:23.732082','2026-08-07 08:33:05.915811','2026-08-07 08:33:05.915811','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T08:01:23.740652+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 08:01:23.732082'),
(75,'kZzQytnD35cyqWv7Z3YsdFA1wZeH81GwhAyhLKrLUZ8','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 08:06:04.982496','2026-08-07 08:37:24.172729','2026-08-07 08:37:24.172729','Revoked',49,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T08:06:04.990286+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 08:06:04.982496'),
(76,'qzLA6k1zqYNLpwQWML-iuHGwGes00oM57RSDdL24z4g','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','2026-08-07 08:09:02.467997','2026-08-07 08:14:03.888069','2026-08-07 08:14:03.888069','Revoked',95,NULL,'{}',0,'2026-08-07 08:09:02.467997'),
(77,'fhLlA9EyEm5HKjvamLGgYm-OgP7h5Zl9UsZyf0O9NAk','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (Linux; Android 15; CPH2591 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/573.0.0.44.88;]','2026-08-07 08:09:18.467702','2026-08-07 08:52:50.151998','2026-08-07 08:52:50.151998','Revoked',94,NULL,'{}',0,'2026-08-07 08:09:18.467702'),
(78,'GymaBUaiqgBV4z5XjSjw5bRuc4ofm-WI7N8bwEZlYHY','112.202.44.41','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','2026-08-07 08:09:25.830378','2026-08-07 16:09:25.828843',NULL,'Active',96,NULL,'{}',0,'2026-08-07 08:09:25.828843'),
(79,'GugkjfsBLXTwnHayWfLMelt6y3I7v9QYS_Smtc4nGcE','111.90.232.145','Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Edg/151.0.0.0 Mobile Safari/537.36','2026-08-07 08:14:03.888069','2026-08-07 08:15:25.207824','2026-08-07 08:15:25.207824','Revoked',95,NULL,'{}',0,'2026-08-07 08:14:03.888069'),
(80,'vkasYoTTvVtBKkcWOdPIqkhT0JAKRUIN9DNX0rJUzEY','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','2026-08-07 08:15:25.220004','2026-08-07 16:15:25.207824',NULL,'Active',95,NULL,'{}',0,'2026-08-07 08:15:25.207824'),
(81,'kDeHRhzcNWwx8-d2Mgg6FtpvWNXSm3SeFCBV-wewZCc','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 08:32:02.748633','2026-08-07 09:02:53.736735','2026-08-07 09:02:53.736735','Revoked',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T08:32:02.774061+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 08:32:02.748633'),
(82,'u_Oc-4R792m-tYBT2kHElNFCL_d4EXd5JGZcQcYUUHs','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 08:33:05.919957','2026-08-07 09:08:20.934954','2026-08-07 09:08:20.934954','Revoked',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T08:33:05.926716+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 08:33:05.917827'),
(83,'nGWvhCqFlHPr1fqGA3zjVfj7Fcne3YqyyPFYLeYN-zU','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 08:37:24.175058','2026-08-07 09:10:00.338136','2026-08-07 09:10:00.338136','Revoked',49,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T08:37:24.179207+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 08:37:24.175058'),
(84,'DHjssYYYSrBK8nIk6C3F2D11ekqgRrBSxZaB0Mq1Utc','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36','2026-08-07 08:52:50.158056','2026-08-07 16:52:50.158056',NULL,'Active',94,NULL,'{}',0,'2026-08-07 08:52:50.158056'),
(85,'CN-GG0hWo06mKmbfEZn5VU_jKbkxlG82Plr6fndeEWE','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 09:02:53.739881','2026-08-07 17:02:53.739881',NULL,'Active',50,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T09:02:53.744263+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 09:02:53.739881'),
(86,'oYB_EzbZaE_qiO3pCa2XsD4AG-hBXsLdhuh4S46A8mI','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','2026-08-07 09:08:20.935998','2026-08-07 17:08:20.935998',NULL,'Active',48,'{\"ip\": \"112.202.44.41\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36\"}','{\"zt_verified_at\": \"2026-08-07T09:08:20.945458+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 09:08:20.935998'),
(87,'n2x-GyNalGStBnuHMFe4eejvSyV-Hk2H_Pe3_GG-kp8','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','2026-08-07 09:10:00.340144','2026-08-07 17:10:00.339142',NULL,'Active',49,'{\"ip\": \"111.90.232.145\", \"ua\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0\"}','{\"zt_verified_at\": \"2026-08-07T09:10:00.345589+00:00\", \"auth_method\": \"mfa_email\"}',1,'2026-08-07 09:10:00.339142');

/*Table structure for table `aid_tracking_post` */

DROP TABLE IF EXISTS `aid_tracking_post`;

CREATE TABLE `aid_tracking_post` (
  `post_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `aid_type` varchar(50) NOT NULL,
  `target_month` varchar(7) NOT NULL,
  `total_expected` decimal(10,2) NOT NULL,
  `total_collected` decimal(10,2) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `notes` longtext NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `archive_id_FK` int(11) NOT NULL,
  `created_by_user_id_FK` int(11) DEFAULT NULL,
  `source_id` int(11) DEFAULT NULL,
  `source_type` varchar(50) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `finish_skip_remaining` tinyint(1) NOT NULL,
  `finish_status` varchar(20) NOT NULL,
  `finish_paid_with_funds` tinyint(1) NOT NULL,
  `deduction_sheet` varchar(100) DEFAULT NULL,
  `deduction_batch_reference` varchar(100) NOT NULL,
  `deduction_payroll_period` varchar(50) NOT NULL,
  `deduction_sheet_uploaded_at` datetime(6) DEFAULT NULL,
  `deduction_remitted_amount` decimal(10,2) DEFAULT NULL,
  `deduction_remitted_at` datetime(6) DEFAULT NULL,
  `deduction_remitted_date` date DEFAULT NULL,
  `deduction_remittance_reference` varchar(100) NOT NULL,
  PRIMARY KEY (`post_id_PK`),
  KEY `AID_TRACKING_POST_archive_id_FK_2bff15c8_fk_transacti` (`archive_id_FK`),
  KEY `AID_TRACKING_POST_created_by_user_id_F_a3a13677_fk_OFFICER_U` (`created_by_user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `aid_tracking_post` */

insert  into `aid_tracking_post`(`post_id_PK`,`aid_type`,`target_month`,`total_expected`,`total_collected`,`is_active`,`notes`,`created_at`,`updated_at`,`archive_id_FK`,`created_by_user_id_FK`,`source_id`,`source_type`,`status`,`finish_skip_remaining`,`finish_status`,`finish_paid_with_funds`,`deduction_sheet`,`deduction_batch_reference`,`deduction_payroll_period`,`deduction_sheet_uploaded_at`,`deduction_remitted_amount`,`deduction_remitted_at`,`deduction_remitted_date`,`deduction_remittance_reference`) values 
(1,'medical_aid','2026-08',20000.00,20000.00,0,'','2026-08-07 08:54:05.102735','2026-08-07 09:01:45.560988',7,48,1,'medical_aid','tracking',1,'approved',0,'deduction_sheets/IMG_20260806_070856.jpg','PAY-2026','2026-07','2026-08-07 09:01:29.802599',20000.00,'2026-08-07 09:01:45.560988','2026-08-07','BPI-69');

/*Table structure for table `album` */

DROP TABLE IF EXISTS `album`;

CREATE TABLE `album` (
  `album_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `description` longtext NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `created_by_id` int(11) DEFAULT NULL,
  `event_id` int(11) DEFAULT NULL,
  `cover_photo_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`album_id_PK`),
  KEY `ALBUM_created_by_id_8df7d8ed_fk_OFFICER_USER_user_id_PK` (`created_by_id`),
  KEY `ALBUM_event_id_160d77b2_fk_EVENT_event_id_PK` (`event_id`),
  KEY `ALBUM_cover_photo_id_c5b9d95a_fk_PHOTO_photo_id_PK` (`cover_photo_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `album` */

/*Table structure for table `announcement` */

DROP TABLE IF EXISTS `announcement`;

CREATE TABLE `announcement` (
  `announcement_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `category` varchar(50) NOT NULL,
  `description` longtext NOT NULL,
  `attachment_path` varchar(500) NOT NULL,
  `attachment_name` varchar(255) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `published_at` datetime(6) NOT NULL,
  `expiry_date` datetime(6) DEFAULT NULL,
  `published_by_user_id_FK` int(11) DEFAULT NULL,
  `image` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`announcement_id_PK`),
  KEY `ANNOUNCEMENT_published_by_user_id_1867ecbe_fk_OFFICER_U` (`published_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `announcement` */

/*Table structure for table `announcement_category` */

DROP TABLE IF EXISTS `announcement_category`;

CREATE TABLE `announcement_category` (
  `category_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`category_id_PK`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `announcement_category` */

/*Table structure for table `attendance` */

DROP TABLE IF EXISTS `attendance`;

CREATE TABLE `attendance` (
  `attendance_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `date` date NOT NULL,
  `check_in_time` time(6) DEFAULT NULL,
  `check_out_time` time(6) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `check_in_method` varchar(20) NOT NULL,
  `member_id_FK` int(11) NOT NULL,
  `event_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`attendance_id_PK`),
  KEY `ATTENDANCE_member_id_FK_977d6132_fk_MEMBER_member_id_PK` (`member_id_FK`),
  KEY `ATTENDANCE_event_id_FK_1fe0a37c_fk_EVENT_event_id_PK` (`event_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `attendance` */

/*Table structure for table `audit_findings_report` */

DROP TABLE IF EXISTS `audit_findings_report`;

CREATE TABLE `audit_findings_report` (
  `audit_report_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `report_title` varchar(255) NOT NULL,
  `report_period` varchar(100) NOT NULL,
  `findings_summary` longtext NOT NULL,
  `report_status` varchar(50) NOT NULL,
  `prepared_date` date NOT NULL,
  `board_submission_date` date DEFAULT NULL,
  `board_meeting_reference` varchar(255) DEFAULT NULL,
  `presentation_status` varchar(50) NOT NULL,
  `certification_status` varchar(50) NOT NULL,
  `certified_by_user_id_FK` int(11) DEFAULT NULL,
  `prepared_by_user_id_FK` int(11) NOT NULL,
  PRIMARY KEY (`audit_report_id_PK`),
  KEY `AUDIT_FINDINGS_REPOR_certified_by_user_id_d3493449_fk_OFFICER_U` (`certified_by_user_id_FK`),
  KEY `AUDIT_FINDINGS_REPOR_prepared_by_user_id__537aa0f1_fk_OFFICER_U` (`prepared_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `audit_findings_report` */

/*Table structure for table `auth_group` */

DROP TABLE IF EXISTS `auth_group`;

CREATE TABLE `auth_group` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `auth_group` */

/*Table structure for table `auth_group_permissions` */

DROP TABLE IF EXISTS `auth_group_permissions`;

CREATE TABLE `auth_group_permissions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `group_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `auth_group_permissions` */

/*Table structure for table `auth_permission` */

DROP TABLE IF EXISTS `auth_permission`;

CREATE TABLE `auth_permission` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `auth_permission` */

/*Table structure for table `auth_user` */

DROP TABLE IF EXISTS `auth_user`;

CREATE TABLE `auth_user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `auth_user` */

/*Table structure for table `auth_user_groups` */

DROP TABLE IF EXISTS `auth_user_groups`;

CREATE TABLE `auth_user_groups` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `group_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `auth_user_groups` */

/*Table structure for table `auth_user_user_permissions` */

DROP TABLE IF EXISTS `auth_user_user_permissions`;

CREATE TABLE `auth_user_user_permissions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `permission_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `auth_user_user_permissions` */

/*Table structure for table `backup_job` */

DROP TABLE IF EXISTS `backup_job`;

CREATE TABLE `backup_job` (
  `job_id` int(11) NOT NULL AUTO_INCREMENT,
  `backup_type` varchar(20) NOT NULL,
  `backup_status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `db_dump_path` varchar(500) DEFAULT NULL,
  `media_archive_path` varchar(500) DEFAULT NULL,
  `metadata_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`metadata_json`)),
  PRIMARY KEY (`job_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `backup_job` */

/*Table structure for table `bylaws_files` */

DROP TABLE IF EXISTS `bylaws_files`;

CREATE TABLE `bylaws_files` (
  `bylaws_file_id` int(11) NOT NULL AUTO_INCREMENT,
  `file_name` varchar(255) NOT NULL,
  `file_type` varchar(100) NOT NULL,
  `file_data` longblob NOT NULL,
  `file_size` int(11) NOT NULL,
  `file_hash` varchar(255) NOT NULL,
  `verification_status` varchar(50) NOT NULL,
  `uploaded_at` datetime(6) NOT NULL,
  `uploaded_by_user_id_FK` int(11) NOT NULL,
  `document_type` varchar(50) NOT NULL,
  `is_public_visible` tinyint(1) NOT NULL,
  PRIMARY KEY (`bylaws_file_id`),
  KEY `bylaws_files_uploaded_by_user_id__a1f6690c_fk_OFFICER_U` (`uploaded_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `bylaws_files` */

/*Table structure for table `category` */

DROP TABLE IF EXISTS `category`;

CREATE TABLE `category` (
  `category_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`category_id_PK`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `category` */

/*Table structure for table `certificate` */

DROP TABLE IF EXISTS `certificate`;

CREATE TABLE `certificate` (
  `certificate_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `certificate_number` varchar(50) NOT NULL,
  `pdf_file` varchar(100) DEFAULT NULL,
  `email_status` varchar(20) NOT NULL,
  `email_sent_at` datetime(6) DEFAULT NULL,
  `email_error` longtext NOT NULL,
  `generated_at` datetime(6) NOT NULL,
  `downloaded_at` datetime(6) DEFAULT NULL,
  `member_id_FK` int(11) NOT NULL,
  `event_id_FK` int(11) NOT NULL,
  PRIMARY KEY (`certificate_id_PK`),
  UNIQUE KEY `certificate_number` (`certificate_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `certificate` */

/*Table structure for table `certificate_settings` */

DROP TABLE IF EXISTS `certificate_settings`;

CREATE TABLE `certificate_settings` (
  `settings_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `president_name` varchar(255) NOT NULL,
  `president_position` varchar(255) NOT NULL,
  `president_signature` varchar(100) DEFAULT NULL,
  `secretary_name` varchar(255) NOT NULL,
  `secretary_position` varchar(255) NOT NULL,
  `secretary_signature` varchar(100) DEFAULT NULL,
  `faculty_regent_name` varchar(255) NOT NULL,
  `faculty_regent_position` varchar(255) NOT NULL,
  `faculty_regent_signature` varchar(100) DEFAULT NULL,
  `organization_logo` varchar(100) DEFAULT NULL,
  `header_text` varchar(255) NOT NULL,
  `footer_text` longtext NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`settings_id_PK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `certificate_settings` */

/*Table structure for table `claimant` */

DROP TABLE IF EXISTS `claimant`;

CREATE TABLE `claimant` (
  `claimant_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `contact_number` varchar(50) DEFAULT NULL,
  `relationship_to_member` varchar(100) NOT NULL,
  `authorization_status` varchar(50) NOT NULL,
  `member_id_FK` int(11) NOT NULL,
  `relationship_group` varchar(20) NOT NULL,
  PRIMARY KEY (`claimant_id_PK`),
  KEY `CLAIMANT_member_id_FK_348a8f79_fk_MEMBER_member_id_PK` (`member_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `claimant` */

/*Table structure for table `contribution` */

DROP TABLE IF EXISTS `contribution`;

CREATE TABLE `contribution` (
  `contribution_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `expected_amount` decimal(10,2) NOT NULL,
  `paid_amount` decimal(10,2) NOT NULL,
  `payment_date` date DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `is_manually_overridden` tinyint(1) NOT NULL,
  `notes` longtext NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `aid_tracking_post_id_FK` int(11) NOT NULL,
  `member_id_FK` int(11) NOT NULL,
  `updated_by_user_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`contribution_id_PK`),
  UNIQUE KEY `CONTRIBUTION_aid_tracking_post_id_FK_member_id_FK_0bdaee32_uniq` (`aid_tracking_post_id_FK`,`member_id_FK`),
  KEY `CONTRIBUTION_member_id_FK_ed361721_fk_MEMBER_member_id_PK` (`member_id_FK`),
  KEY `CONTRIBUTION_updated_by_user_id_F_158d64bf_fk_OFFICER_U` (`updated_by_user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `contribution` */

insert  into `contribution`(`contribution_id_PK`,`expected_amount`,`paid_amount`,`payment_date`,`status`,`is_manually_overridden`,`notes`,`updated_at`,`aid_tracking_post_id_FK`,`member_id_FK`,`updated_by_user_id_FK`) values 
(1,10000.00,10000.00,'2026-08-07','PAID',0,'','2026-08-07 09:01:52.949189',1,2,50),
(2,10000.00,10000.00,'2026-08-07','PAID',0,'','2026-08-07 09:01:52.953990',1,3,50);

/*Table structure for table `death_aid` */

DROP TABLE IF EXISTS `death_aid`;

CREATE TABLE `death_aid` (
  `death_aid_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `claim_date` date NOT NULL,
  `claim_type` varchar(50) NOT NULL,
  `deceased_name` varchar(255) NOT NULL,
  `relationship_to_member` varchar(100) NOT NULL,
  `benefit_amount` decimal(10,2) NOT NULL,
  `document_status` varchar(50) NOT NULL,
  `status` varchar(50) NOT NULL,
  `president_decision` varchar(50) DEFAULT NULL,
  `release_reference` varchar(100) DEFAULT NULL,
  `acknowledgement_reference` varchar(100) DEFAULT NULL,
  `claimant_id_FK` int(11) NOT NULL,
  `member_id_FK` int(11) NOT NULL,
  `auditor_verified_by_user_id_FK` int(11) DEFAULT NULL,
  `president_decided_by_user_id_FK` int(11) DEFAULT NULL,
  `released_by_user_id_FK` int(11) DEFAULT NULL,
  `treasurer_validated_by_user_id_FK` int(11) DEFAULT NULL,
  `bill_amount` decimal(10,2) DEFAULT NULL,
  `funeral_location` varchar(255) NOT NULL,
  `interment_date` date DEFAULT NULL,
  `relationship_group` varchar(20) NOT NULL,
  `disbursement_source` varchar(20) DEFAULT NULL,
  `date_of_death` date DEFAULT NULL,
  PRIMARY KEY (`death_aid_id_PK`),
  KEY `DEATH_AID_claimant_id_FK_f0b13e0c_fk_CLAIMANT_claimant_id_PK` (`claimant_id_FK`),
  KEY `DEATH_AID_member_id_FK_ba2eae1b_fk_MEMBER_member_id_PK` (`member_id_FK`),
  KEY `DEATH_AID_auditor_verified_by__80ca4f33_fk_OFFICER_U` (`auditor_verified_by_user_id_FK`),
  KEY `DEATH_AID_president_decided_by_bcc1b2ff_fk_OFFICER_U` (`president_decided_by_user_id_FK`),
  KEY `DEATH_AID_treasurer_validated__54e09fac_fk_OFFICER_U` (`treasurer_validated_by_user_id_FK`),
  KEY `DEATH_AID_released_by_user_id_FK_c16b5c5b` (`released_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `death_aid` */

/*Table structure for table `department` */

DROP TABLE IF EXISTS `department`;

CREATE TABLE `department` (
  `department_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `code` varchar(50) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `head_officer_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`department_id_PK`),
  UNIQUE KEY `code` (`code`),
  KEY `DEPARTMENT_head_officer_id_FK_9ade364b_fk_OFFICER_U` (`head_officer_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `department` */

/*Table structure for table `django_admin_log` */

DROP TABLE IF EXISTS `django_admin_log`;

CREATE TABLE `django_admin_log` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext DEFAULT NULL,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint(5) unsigned NOT NULL CHECK (`action_flag` >= 0),
  `change_message` longtext NOT NULL,
  `content_type_id` int(11) DEFAULT NULL,
  `user_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `django_admin_log` */

/*Table structure for table `django_content_type` */

DROP TABLE IF EXISTS `django_content_type`;

CREATE TABLE `django_content_type` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `django_content_type` */

insert  into `django_content_type`(`id`,`app_label`,`model`) values 
(1,'core_system','memberregistrationrequest'),
(2,'core_system','membershipfee');

/*Table structure for table `django_migrations` */

DROP TABLE IF EXISTS `django_migrations`;

CREATE TABLE `django_migrations` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `django_migrations` */

/*Table structure for table `django_session` */

DROP TABLE IF EXISTS `django_session`;

CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `django_session` */

insert  into `django_session`(`session_key`,`session_data`,`expire_date`) values 
('1bhhhyj8v6uhebpymrl3vb8yx1t72ntp','eyJvZmZpY2VyX2lkIjo0OSwicm9sZSI6IlRyZWFzdXJlciIsImFjY2Vzc190b2tlbiI6Im4yeC1HeU5hbEdTdEJudUhNRmU0ZWVqdlN5Vi1IazJIX1BlM19HRy1rcDgifQ:1wsGaW:wsZdkrIOItYl6L4lgax3bTeRCiMYzdqYkECxge9V8MY','2026-08-21 09:10:00.365608'),
('1m861lwofc1l1cx6cdna96mhuj1vfmsq','eyJvZmZpY2VyX2lkIjo5Mywicm9sZSI6Ik1lbWJlciJ9:1wsCeV:hWhfEn6Hgr-ttHS86Lr9JfQwCBx9VZcZ0Yepe7Um3rg','2026-08-21 04:57:51.270472'),
('5l62decqakkpqz802165rnhus6zlnyau','eyJvZmZpY2VyX2lkIjo5Mywicm9sZSI6Ik1lbWJlciJ9:1wsFYh:cJUESlmv90Birn4BXj05y1DVdBrrRJK8ADTxXV34q-A','2026-08-21 08:04:03.728705'),
('7kopoatvw7dpfouy9dugwhzc7oeyt5w9','eyJvZmZpY2VyX2lkIjo0OCwicm9sZSI6IlByZXNpZGVudCIsImFjY2Vzc190b2tlbiI6InZvWktOUTBHbTZobE5OYnRGVnl0RUE1RnBuMHQ2cUg3VVV0TERDSmFiejAifQ:1wsCeD:59j_I6wfVlAbZlVZ6NxyvJtLKC0ylSPXZD1Nl3AAeAU','2026-08-21 04:57:33.218874'),
('bsjwd04sc5nowpf4lzz1tt0ni4uw34xa','eyJvZmZpY2VyX2lkIjo0OCwicm9sZSI6IlByZXNpZGVudCIsImFjY2Vzc190b2tlbiI6Im9ZQl9FemJaYUVfcWlPM3BDYTJYc0Q0QUctaEJYc0xkaHVoNFM0NkE4bUkifQ:1wsGYu:0YvKqsahU6g1VDBg2SHQcWkERlqtJr4XM1YIRKdBgdo','2026-08-21 09:08:20.968845'),
('bw2e9kyxutx7cpni8eopdkxf1w2wxw33','eyJhY2Nlc3NfdG9rZW4iOiJHdWdramZzQkxYVHduSGF5V2ZMTWVsdDZ5M0k3djlRWVNfU210YzRuR2NFIiwib2ZmaWNlcl9pZCI6OTUsInJvbGUiOiJNZW1iZXIifQ:1wsFiN:_I02bCQSFSViHIkk5n3Jh_6LdjCMJ-aYRXLKktIVN8E','2026-08-21 08:14:03.914032'),
('gse4v6xj89btzbwwukofeu3csl3qm6d4','eyJvZmZpY2VyX2lkIjo1MCwicm9sZSI6IkF1ZGl0b3IiLCJhY2Nlc3NfdG9rZW4iOiJDTi1HRzBoV28wNm1LbWJmRVpuNVZVX2pLYmt4bEc4MlBscjZmbmRlRVdFIn0:1wsGTd:x73gDU20gPsjbORkWLPWMJ94Hv07OCt0DNvzFD4AzJA','2026-08-21 09:02:53.755536'),
('i993oglw0yc0lq289psmlg7167j4dd6b','eyJvZmZpY2VyX2lkIjo5NCwicm9sZSI6Ik1lbWJlciJ9:1wsG8N:aVH_NP3E-H5AOmVz8bHgEaQgQgGFl4D9_zFA78HpFOc','2026-08-21 08:40:55.541521'),
('id0jalpq2nyddso0hp780xo78wsg95sk','eyJvZmZpY2VyX2lkIjo5Miwicm9sZSI6Ik1lbWJlciJ9:1wsBbq:t4Ag8fiuAiKSwlG6zjvwltB9fA-T-q-aTkiozcAgnk4','2026-08-21 03:51:02.490846'),
('j8znlyh13xwq21yrls0k2rhswab3ebtz','eyJvZmZpY2VyX2lkIjo5Miwicm9sZSI6Ik1lbWJlciJ9:1wsGG9:Yric4vvUj1dGwdQwKmbDLkB5Lslp-UOtv-HRL4T07x8','2026-08-21 08:48:57.570023'),
('k9um7xzz2w30sckk3xtzvx19joe8ck9z','eyJfc2Vzc2lvbl9leHBpcnkiOjYwMCwiYWNjZXNzX3Rva2VuIjoiTER1emFUREhZTWxkMU5tVmxLX2tyZFlUYkRrSVhQQ2FFYkljRC0wY1hUayIsIm9mZmljZXJfaWQiOjkyLCJyb2xlIjoiTWVtYmVyIn0:1wsDLf:YukckP2x23K5CxwM_sMYlqJ8WXu7_PqVefEaufvn5po','2026-08-07 05:52:27.450641'),
('lw7ed242ypopvslzoezbyp5qm5u6mtun','eyJvZmZpY2VyX2lkIjo5NSwicm9sZSI6Ik1lbWJlciIsImFjY2Vzc190b2tlbiI6InZrYXNZb1RUdlZ0QktrY1dPZFBJcWtoVDBKQUtSVUlOOUROWDBySlV6RVkifQ:1wsFjl:41sB5Es5LeWphyKiEiAUY0oIgSnivZtonjeVB-5xu3c','2026-08-21 08:15:29.635829'),
('niwwmhawth220vsde8diwzl6uy30g4zf','eyJvZmZpY2VyX2lkIjo5Niwicm9sZSI6Ik1lbWJlciJ9:1wsG9f:LA-eJw0vCe5TFqUYbCYEI6iqPCVJBCUwKyaObMfNZmA','2026-08-21 08:42:15.172900'),
('rxg8kzvy1y0ubxi8u1x1102mucr2ynfo','eyJhY2Nlc3NfdG9rZW4iOiJESGpzc1lZWVNyQks4bklrNkMzRjJEMTFla3FnUnJCU3haYUIwTXExVXRjIiwib2ZmaWNlcl9pZCI6OTQsInJvbGUiOiJNZW1iZXIifQ:1wsGJu:Fo_cLp7F4yXkq2l6k-Rn8QHowrftIf1ekOFGXC1PsL0','2026-08-21 08:52:50.207743');

/*Table structure for table `document` */

DROP TABLE IF EXISTS `document`;

CREATE TABLE `document` (
  `document_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `description` longtext NOT NULL,
  `document_type` varchar(50) NOT NULL,
  `category` varchar(100) NOT NULL,
  `keywords` varchar(500) NOT NULL,
  `tags` varchar(500) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `file_name` varchar(255) NOT NULL,
  `file_size` bigint(20) DEFAULT NULL,
  `file_type` varchar(50) NOT NULL,
  `version` varchar(20) NOT NULL,
  `uploaded_at` datetime(6) NOT NULL,
  `retention_period` date DEFAULT NULL,
  `is_archived` tinyint(1) NOT NULL,
  `uploaded_by_user_id_FK` int(11) DEFAULT NULL,
  `is_public_visible` tinyint(1) NOT NULL,
  PRIMARY KEY (`document_id_PK`),
  KEY `DOCUMENT_uploaded_by_user_id__2d5af3d8_fk_OFFICER_U` (`uploaded_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `document` */

/*Table structure for table `document_activity` */

DROP TABLE IF EXISTS `document_activity`;

CREATE TABLE `document_activity` (
  `activity_id` int(11) NOT NULL AUTO_INCREMENT,
  `action` varchar(50) NOT NULL,
  `officer_name` varchar(255) NOT NULL,
  `details` longtext NOT NULL,
  `timestamp` datetime(6) NOT NULL,
  `document_id_FK` int(11) DEFAULT NULL,
  `officer_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`activity_id`),
  KEY `DOCUMENT_ACTIVITY_document_id_FK_2c1d21b5_fk_DOCUMENT_` (`document_id_FK`),
  KEY `DOCUMENT_ACTIVITY_officer_id_FK_e46a0d41_fk_OFFICER_U` (`officer_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `document_activity` */

/*Table structure for table `document_pin` */

DROP TABLE IF EXISTS `document_pin`;

CREATE TABLE `document_pin` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `pinned_at` datetime(6) NOT NULL,
  `document_id_FK` int(11) NOT NULL,
  `officer_id_FK` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `DOCUMENT_PIN_document_id_FK_officer_id_FK_776da9b1_uniq` (`document_id_FK`,`officer_id_FK`),
  KEY `DOCUMENT_PIN_officer_id_FK_36d52f31_fk_OFFICER_USER_user_id_PK` (`officer_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `document_pin` */

/*Table structure for table `event` */

DROP TABLE IF EXISTS `event`;

CREATE TABLE `event` (
  `event_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `description` longtext NOT NULL,
  `venue` varchar(255) NOT NULL,
  `event_date` date NOT NULL,
  `event_time` time(6) NOT NULL,
  `end_time` time(6) DEFAULT NULL,
  `event_type` varchar(100) NOT NULL,
  `status` varchar(20) NOT NULL,
  `attendance_open` tinyint(1) NOT NULL,
  `attendance_closed` tinyint(1) NOT NULL,
  `quorum_required` int(11) NOT NULL,
  `quorum_reached` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `created_by_user_id_FK` int(11) DEFAULT NULL,
  `auto_generate_certificates` tinyint(1) NOT NULL,
  `certificate_issue_date` date DEFAULT NULL,
  `certificate_prefix` varchar(20) NOT NULL,
  `given_place` varchar(255) NOT NULL,
  PRIMARY KEY (`event_id_PK`),
  KEY `EVENT_created_by_user_id_FK_ace80cb6_fk_OFFICER_USER_user_id_PK` (`created_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `event` */

/*Table structure for table `event_type` */

DROP TABLE IF EXISTS `event_type`;

CREATE TABLE `event_type` (
  `event_type_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`event_type_id_PK`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `event_type` */

/*Table structure for table `financial_document_archive` */

DROP TABLE IF EXISTS `financial_document_archive`;

CREATE TABLE `financial_document_archive` (
  `document_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `related_module` varchar(100) NOT NULL,
  `related_record_id` int(11) NOT NULL,
  `document_type` varchar(100) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `file_hash` varchar(255) NOT NULL,
  `verification_status` varchar(50) NOT NULL,
  `uploaded_at` datetime(6) NOT NULL,
  `uploaded_by_user_id_FK` int(11) NOT NULL,
  `file_name` varchar(255) NOT NULL,
  `file_type` varchar(100) NOT NULL,
  PRIMARY KEY (`document_id_PK`),
  KEY `FINANCIAL_DOCUMENT_A_uploaded_by_user_id__2e803a5e_fk_OFFICER_U` (`uploaded_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `financial_document_archive` */

/*Table structure for table `fund_transaction` */

DROP TABLE IF EXISTS `fund_transaction`;

CREATE TABLE `fund_transaction` (
  `transaction_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `direction` varchar(10) NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `source_type` varchar(50) NOT NULL,
  `source_id` int(11) NOT NULL,
  `description` varchar(255) NOT NULL,
  `reference_number` varchar(100) DEFAULT NULL,
  `recorded_at` datetime(6) NOT NULL,
  `recorded_by_user_id_FK` int(11) NOT NULL,
  PRIMARY KEY (`transaction_id_PK`),
  KEY `FUND_TRANSACTION_recorded_by_user_id__4d5f9ffd_fk_OFFICER_U` (`recorded_by_user_id_FK`),
  KEY `FUND_TRANSA_directi_c179cb_idx` (`direction`),
  KEY `FUND_TRANSA_source__6023fe_idx` (`source_type`,`source_id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `fund_transaction` */

insert  into `fund_transaction`(`transaction_id_PK`,`direction`,`amount`,`source_type`,`source_id`,`description`,`reference_number`,`recorded_at`,`recorded_by_user_id_FK`) values 
(1,'inflow',100.00,'membership_fee',1,'Jayjay D Mariano - Membership Fee (registration)','REG-20260807080546-21-232323','2026-08-07 08:07:23.105108',48),
(2,'inflow',100.00,'membership_fee',2,'Bartholomew Q Badongkadonks - Membership Fee (registration)','REG-20260807080552-bart','2026-08-07 08:07:30.397057',48),
(3,'inflow',100.00,'membership_fee',3,'JUSTIN VON T VERGARA - Membership Fee (registration)','REG-20260807080539-142joe','2026-08-07 08:07:36.671793',48),
(4,'inflow',50.00,'monthly_dues',2,'Jayjay D Mariano (Monthly Dues)',NULL,'2026-08-07 08:26:20.678977',48),
(5,'inflow',50.00,'monthly_dues',1,'Jayjay D Mariano (Monthly Dues)',NULL,'2026-08-07 08:26:29.678885',48),
(6,'inflow',50.00,'monthly_dues',3,'Jayjay D Mariano (Monthly Dues)',NULL,'2026-08-07 08:33:57.139144',48),
(7,'inflow',50.00,'monthly_dues',4,'Bartholomew Q Badongkadonks (Monthly Dues)',NULL,'2026-08-07 08:34:22.331667',48),
(8,'inflow',50.00,'monthly_dues',5,'JUSTIN VON T VERGARA (Monthly Dues)',NULL,'2026-08-07 08:34:22.331667',48),
(9,'inflow',50.00,'monthly_dues',6,'JUSTIN VON T VERGARA (Monthly Dues)',NULL,'2026-08-07 08:38:21.011240',48),
(10,'inflow',20000.00,'salary_deduction_remittance',1,'Salary deduction remittance ref BPI-69 for aid post 1','BPI-69','2026-08-07 09:01:45.562053',49),
(11,'inflow',10000.00,'contribution',1,'Aid contribution — Bartholomew Q Badongkadonks for Jayjay D Mariano\'s Medical Aid','AID-1-C-1','2026-08-07 09:07:47.104840',50),
(12,'inflow',10000.00,'contribution',2,'Aid contribution — JUSTIN VON T VERGARA for Jayjay D Mariano\'s Medical Aid','AID-1-C-2','2026-08-07 09:07:47.104840',50),
(13,'outflow',20000.00,'medical_aid',1,'Aid disbursement — Jayjay D Mariano (medical_aid)',NULL,'2026-08-07 09:12:01.005824',49);

/*Table structure for table `global_audit_trail` */

DROP TABLE IF EXISTS `global_audit_trail`;

CREATE TABLE `global_audit_trail` (
  `trail_id` int(11) NOT NULL AUTO_INCREMENT,
  `table_name` varchar(100) NOT NULL,
  `record_id` int(11) NOT NULL,
  `action` varchar(50) NOT NULL,
  `old_values` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`old_values`)),
  `new_values` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`new_values`)),
  `actor_type` varchar(50) NOT NULL,
  `actor_id` int(11) DEFAULT NULL,
  `actor_name` varchar(255) NOT NULL,
  `ip_address` char(39) DEFAULT NULL,
  `device_info` varchar(255) DEFAULT NULL,
  `notes` longtext DEFAULT NULL,
  `timestamp` datetime(6) NOT NULL,
  `document_archive_id_FK` int(11) DEFAULT NULL,
  `entry_hash` varchar(64) DEFAULT NULL,
  `hmac_signature` varchar(64) DEFAULT NULL,
  `previous_hash` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`trail_id`),
  KEY `GLOBAL_AUDI_table_n_f2953e_idx` (`table_name`,`record_id`,`timestamp`),
  KEY `GLOBAL_AUDIT_TRAIL_document_archive_id__cd699f95_fk_FINANCIAL` (`document_archive_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=114 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `global_audit_trail` */

insert  into `global_audit_trail`(`trail_id`,`table_name`,`record_id`,`action`,`old_values`,`new_values`,`actor_type`,`actor_id`,`actor_name`,`ip_address`,`device_info`,`notes`,`timestamp`,`document_archive_id_FK`,`entry_hash`,`hmac_signature`,`previous_hash`) values 
(1,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:06:08.927855',NULL,'da19c3e63c801c2ebc1798aa29b95db03ed16edd660f3600b4488a67c6add88e','325eadd99e4828b252cff4107cb54dec28a5255694e2ce076fed2e9ccdcb698f','0000000000000000000000000000000000000000000000000000000000000000'),
(2,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (0 records)','2026-08-07 08:06:08.928370',NULL,'671fb8002f5ca702942c76d0c5666ea903e7cf42a7ea75832d6660390d73871b','a1c6156f7e9b97290c456e279850d22ae1e6ad420a9fa2b0650a755780db8e6e','0000000000000000000000000000000000000000000000000000000000000000'),
(3,'member_registration_request',3,'TREASURER_VERIFIED',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Treasurer verified registration request for Bartholomew Q Badongkadonks','2026-08-07 08:06:20.181854',NULL,'e26a6cc003b36148f5985c21ec10edc98e34765fffde6c554b082c036989d167','6ae785b22cb4a2eb9facd3b5225cba1de462494d4397f257f877f7fd5207af89','671fb8002f5ca702942c76d0c5666ea903e7cf42a7ea75832d6660390d73871b'),
(4,'member_registration_request',2,'TREASURER_VERIFIED',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Treasurer verified registration request for Jayjay D Mariano','2026-08-07 08:06:24.374427',NULL,'57e643fbe1111dc695f360525df782eb9c947201b5f1f40c17688745784216dc','c5110cad10b9d73c63bc82ceb7c5be1f92056e0605ce99045bec0e28efb868d2','e26a6cc003b36148f5985c21ec10edc98e34765fffde6c554b082c036989d167'),
(5,'member_registration_request',1,'TREASURER_VERIFIED',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Treasurer verified registration request for JUSTIN VON T VERGARA','2026-08-07 08:06:30.110229',NULL,'ff149006befffed9a552ae6b219f61e1c337e04758a73a834bc48be437cc2e67','4bb4ef9315e5fdbd2ce68c00f1a15d5585ce8547d5eff671e17d2d4aee2983d6','57e643fbe1111dc695f360525df782eb9c947201b5f1f40c17688745784216dc'),
(6,'member_registration_request',3,'AUDITOR_VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Auditor verified registration request for Bartholomew Q Badongkadonks','2026-08-07 08:06:40.967832',NULL,'7e67acff131268354615b0071f6598ba04e0c3f4bd4031167f860ead4985ce04','776e83e0d46c86c3dd8deeeb662cca4815f5775aa874df4d95b85c84392550c1','ff149006befffed9a552ae6b219f61e1c337e04758a73a834bc48be437cc2e67'),
(7,'member_registration_request',2,'AUDITOR_VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Auditor verified registration request for Jayjay D Mariano','2026-08-07 08:06:55.630021',NULL,'24646914f5737fcbd4d1425337e60b04db73cfd0f748204a1a1f339033d09c74','868f7721fff967b1a99f80a04c815d812452f07898079aab7d095ea8063e48eb','7e67acff131268354615b0071f6598ba04e0c3f4bd4031167f860ead4985ce04'),
(8,'member_registration_request',1,'AUDITOR_VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Auditor verified registration request for JUSTIN VON T VERGARA','2026-08-07 08:07:08.363597',NULL,'55db0ec7f8afb2590c153cb9ff9475576a41bdc870545ace21114277047709a2','2c9e953becb78bde2328202c3133fa2f9080dfadd8879c6afa06bd3446379de3','24646914f5737fcbd4d1425337e60b04db73cfd0f748204a1a1f339033d09c74'),
(9,'member_registration_request',2,'PRESIDENT_APPROVED',NULL,'{\"member_id\": \"1\", \"officer_user_id\": \"94\", \"fee_id\": \"1\", \"status\": \"President Approved\"}','President',48,'President Account','112.202.44.41',NULL,'President approved registration for Jayjay D Mariano. Member/OfficerUser/MembershipFee created.','2026-08-07 08:07:25.879466',NULL,'338fb6aa1eded8eb34ad9da02fc36d69afcf3a21b59d972b5aa81da79e1b6104','747ddf7864388152871d8738584e1be044d11cf2664584b836388e87909c1013','55db0ec7f8afb2590c153cb9ff9475576a41bdc870545ace21114277047709a2'),
(10,'member_registration_request',3,'PRESIDENT_APPROVED',NULL,'{\"member_id\": \"2\", \"officer_user_id\": \"95\", \"fee_id\": \"2\", \"status\": \"President Approved\"}','President',48,'President Account','112.202.44.41',NULL,'President approved registration for Bartholomew Q Badongkadonks. Member/OfficerUser/MembershipFee created.','2026-08-07 08:07:30.441008',NULL,'d1c5b9a61f10d8a2c6b74617bf128dc0a5cfe851d85124f996a57343486005d6','4cdaf5957a8980d3773825f5bb8733cb9f3680b1d09a1958293a85d26184ab4b','338fb6aa1eded8eb34ad9da02fc36d69afcf3a21b59d972b5aa81da79e1b6104'),
(11,'member_registration_request',1,'PRESIDENT_APPROVED',NULL,'{\"member_id\": \"3\", \"officer_user_id\": \"96\", \"fee_id\": \"3\", \"status\": \"President Approved\"}','President',48,'President Account','112.202.44.41',NULL,'President approved registration for JUSTIN VON T VERGARA. Member/OfficerUser/MembershipFee created.','2026-08-07 08:07:36.680923',NULL,'e314269839dee6f9dcd371e572d8665abee3fef173d9da2d2ea8c901b9da2e50','8bb9968fd0b4f5d14a3f86fa2ce71404620f5fda8eae08f79f49ecdd564095da','d1c5b9a61f10d8a2c6b74617bf128dc0a5cfe851d85124f996a57343486005d6'),
(12,'officer_user',95,'PASSWORD_CHANGED',NULL,NULL,'Member',95,'Bartholomew Q Badongkadonks','111.90.232.145',NULL,'Password changed via change-password flow.','2026-08-07 08:09:29.919767',NULL,'1f3efad2b986a3458129160ae8dfae28617553ec938be37891b52ccb8554ea9d','aa4e78ee3da8043cb674a58b3462243528003c3c522ffcb6670a61c0900266ea','e314269839dee6f9dcd371e572d8665abee3fef173d9da2d2ea8c901b9da2e50'),
(13,'officer_user',94,'PASSWORD_CHANGED',NULL,NULL,'Member',94,'Jayjay D Mariano','2405:8d40:4804:6e0c:4780:f302:3845:799e',NULL,'Password changed via change-password flow.','2026-08-07 08:09:51.337697',NULL,'2ff5f59c7b6dd18124ffe74751d0c89cdcb12be60634283fedb7987c98592d32','4003c03effe1e1d1ba3116f67ed75a137edd69acd0cb704d38f90f4542a049a3','1f3efad2b986a3458129160ae8dfae28617553ec938be37891b52ccb8554ea9d'),
(14,'officer_user',96,'PASSWORD_CHANGED',NULL,NULL,'Member',96,'JUSTIN VON T VERGARA','112.202.44.41',NULL,'Password changed via change-password flow.','2026-08-07 08:09:52.912914',NULL,'fa281f261cadfb09e0f9e4ddcf91c1437654ef1e823a05e0238025b226a7915a','f457434478f75594fb0f971ccc2fe3605eb2f08d568519288d36efe702c066e2','2ff5f59c7b6dd18124ffe74751d0c89cdcb12be60634283fedb7987c98592d32'),
(15,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:20:26.702190',NULL,'195fa7afd795b0885f528c9158d15142b4835496f95f83eacac56e67afc8bd62','d2c85c37b79bcbc6dcfef628187a5114f3d9926a15db538948cffe2bddc6149f','fa281f261cadfb09e0f9e4ddcf91c1437654ef1e823a05e0238025b226a7915a'),
(16,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:20:26.727741',NULL,'83beee7d70aea8d3d9f7f956f2699123e81cedcfec58835ed4aa52cbb2b218c0','fd7c14f237b5b215fe7cba264751b950e1c5230a18cbd65131b64096c82f7205','195fa7afd795b0885f528c9158d15142b4835496f95f83eacac56e67afc8bd62'),
(17,'monthly_dues',2,'Treasurer Approved',NULL,'{\"member\": {\"id\": 1, \"name\": \"Jayjay D Mariano\"}, \"month_covered\": \"2026-10\", \"amount\": \"50.00\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'','2026-08-07 08:20:58.231658',NULL,'244f5214fc76c6e4e9a456081919e8fa532d3cfb66f50bcb68e256e7e97e5ada','d5c902a4801fc71628ead0ab3877f1465610b234c50959f9608d787ec1b93e00','83beee7d70aea8d3d9f7f956f2699123e81cedcfec58835ed4aa52cbb2b218c0'),
(18,'monthly_dues',1,'Treasurer Approved',NULL,'{\"member\": {\"id\": 1, \"name\": \"Jayjay D Mariano\"}, \"month_covered\": \"2026-09\", \"amount\": \"50.00\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'','2026-08-07 08:21:07.183278',NULL,'f2410cd2c0364848f1d6a86bf1d0c34d77553a0c84a45c1880b03f10618becde','fcbb59f84c9e10713fc5e6a8d688aa3f69c8248f1b171ecfe2ec3447500716cb','244f5214fc76c6e4e9a456081919e8fa532d3cfb66f50bcb68e256e7e97e5ada'),
(19,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:21:14.594238',NULL,'bc059bc684d58b8c6fad9ad5876a1f44963f34ba3d461dca8464d5be33b29e2e','e71e54f50d4168030362d8b0856055a1300121d084988abd36c7e5180bbceb4c','f2410cd2c0364848f1d6a86bf1d0c34d77553a0c84a45c1880b03f10618becde'),
(20,'monthly_dues',2,'VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Reviewed by JAYEM REOJANO','2026-08-07 08:22:01.108756',NULL,'21cfc9450d4b031ecd6fec5cd1dd92de9ff135249b58f006d03f7c8a23a8b3a7','7075e69fc640f892698abee37cfc2bc17bd2f885af5e569f88972a00753a26c6','bc059bc684d58b8c6fad9ad5876a1f44963f34ba3d461dca8464d5be33b29e2e'),
(21,'monthly_dues',1,'VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Reviewed by JAYEM REOJANO','2026-08-07 08:22:01.108756',NULL,'76356ddf9aecd26edd93d6a19ec1d7ef8252c7408a71c8c526a84be664c9fa78','d3ebbd722b3054dd39f51c61b8871d8d2c2038788e0c56d24280a416b28c7afc','21cfc9450d4b031ecd6fec5cd1dd92de9ff135249b58f006d03f7c8a23a8b3a7'),
(22,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:22:01.984690',NULL,'b8d75bf52a92392beb27ea57576a6e6e9eeb612a4eabdb5359c7d1f9902b13fe','df8d51c0eae5d9ad4429d10869e6b4f486f0bf0751cc2fea9af05e26bdb2315e','76356ddf9aecd26edd93d6a19ec1d7ef8252c7408a71c8c526a84be664c9fa78'),
(23,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:22:02.123247',NULL,'919c6752139cc5f055711e91c94ac224546428b34f39a5f9302266ac967dc2d6','1d6ff460cd62ec834d0f31f94a5ef661519cd9d3ab6c74dddb44c9ba0af983df','b8d75bf52a92392beb27ea57576a6e6e9eeb612a4eabdb5359c7d1f9902b13fe'),
(24,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:22:02.427968',NULL,'00fd11d1b2ef0e821cb1b1c7e37314c89b4322c17b236ac7aa45fb84f9cf8f3b','755319b3bee855d6a63aecd77fe4c50e946ed8cfa3a448dd2bf5a36d1a050973','919c6752139cc5f055711e91c94ac224546428b34f39a5f9302266ac967dc2d6'),
(25,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:22:02.816287',NULL,'1f8b15e9f8f29d280fb069b41f7783eca9bff9664c95ea9eb579e446ad403904','2e2351ef56de89d30885f7dab14c47780868e8f7aa8aa90b66abcd5f1d88d1fd','00fd11d1b2ef0e821cb1b1c7e37314c89b4322c17b236ac7aa45fb84f9cf8f3b'),
(26,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:22:03.775730',NULL,'c74f871957c77f48530d6759ed21d68ea4c0a94508459a8001890c7e63b13626','bf25f775381dff9dfcf4984fc3566080536d3e2d486f5d48c8b1cd224310026c','1f8b15e9f8f29d280fb069b41f7783eca9bff9664c95ea9eb579e446ad403904'),
(27,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:22:04.084042',NULL,'b772600e145273325ea128e753c6c8aa3d6df538c4cc7607176542a647c12f6b','63c3cd98dfb7884ba238bc2be7aabb7f8fe415acab42d01549d4897341134ad7','c74f871957c77f48530d6759ed21d68ea4c0a94508459a8001890c7e63b13626'),
(28,'monthly_dues',2,'APPROVED',NULL,NULL,'President',48,'President Account','112.202.44.41',NULL,NULL,'2026-08-07 08:26:20.678977',NULL,'5c99ec7ac3435120426a88618291c259c92b291705d1922f4cff177ea17fd1f4','87ba663ef669b72174b68df19ccd2fa55128dcb78344640ef82aeb21eec67c91','b772600e145273325ea128e753c6c8aa3d6df538c4cc7607176542a647c12f6b'),
(29,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:26:21.488051',NULL,'ebf718abdfc824184c6466d7a76bdbb08f08191d3cdb881bba2e5192e3608be3','81b6dc7db6d83c8296691cdafe3e11e025a30036410a501d48a6e8e1b6e8f27c','5c99ec7ac3435120426a88618291c259c92b291705d1922f4cff177ea17fd1f4'),
(30,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:26:21.718194',NULL,'9759967ade5f9886d64b0dc38a05d9dac4852dc1e74e788f8f027d7e14a3a9ea','a8265de2f96a93a31be6c9e6cd374c5ec27be0a53dfd772730a239eb7586b1eb','ebf718abdfc824184c6466d7a76bdbb08f08191d3cdb881bba2e5192e3608be3'),
(31,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:26:21.992414',NULL,'86c0fc39fb42a940bf25daf9f4aa8d24cf85ed34474a3e889e2e9acad0d80075','4091ec75a2ba84db38322f06d422093857a34ee086b045a6da4dba83b9fd9ee1','9759967ade5f9886d64b0dc38a05d9dac4852dc1e74e788f8f027d7e14a3a9ea'),
(32,'monthly_dues',1,'APPROVED',NULL,NULL,'President',48,'President Account','112.202.44.41',NULL,'heheheh','2026-08-07 08:26:36.246176',NULL,'67c693409cfb07efc3bae76a89628a375afa22f1e23df3936a075d61c4f3cd0f','4efed3e70f108080d0cfbc00a5a74d8caabc8948dd70556da642b12861becd2f','86c0fc39fb42a940bf25daf9f4aa8d24cf85ed34474a3e889e2e9acad0d80075'),
(33,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:26:36.905190',NULL,'e37c15cdb4b90bef172c3485e5282c0b502804df56acf3ae437264502e23d978','ffdaec1a7e623a45c0ad23803e744d7ca9ce9e51b2a34f3e861b6fd3351dc34c','67c693409cfb07efc3bae76a89628a375afa22f1e23df3936a075d61c4f3cd0f'),
(34,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:26:37.541146',NULL,'2711dcaeac56a620724e6bff21b38e853980cafe21534ea6f9e546fcf698cbc6','d77894cac600366c5c6e1d19fb8d91ddef51fb713ae521a8b20dcc4abbba1e05','e37c15cdb4b90bef172c3485e5282c0b502804df56acf3ae437264502e23d978'),
(35,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:26:37.910450',NULL,'f3579052c6127eee08ed7205a45de5a6a55fcf41a9c7c89232202bb181925bb0','d2ae57ef8e39deb43a8eb01ed53295a2aecc5ff737125383829414d07f99bf11','2711dcaeac56a620724e6bff21b38e853980cafe21534ea6f9e546fcf698cbc6'),
(36,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:26:51.880172',NULL,'5e42502b18cb34db3fa19984a61aaefaa8e34d851625414c3caa8f2fb3178d24','0166918967857a5fc5460c4a21d20978031490fac159288c5da9a285c6095fa8','f3579052c6127eee08ed7205a45de5a6a55fcf41a9c7c89232202bb181925bb0'),
(37,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:26:51.919922',NULL,'38c92e7cd43a75e4849441a0e4a23995a8dd13635cab866e55cbbf21c3b85813','465089658dc927def4240144d3e7752624b95fc718258cf98e7c79bc280f9608','5e42502b18cb34db3fa19984a61aaefaa8e34d851625414c3caa8f2fb3178d24'),
(38,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:27:04.653465',NULL,'2711b2890f8ec2c707ae23f8c1f2bd9f73414753f5e5370ccc67511288bab49d','b824a680b211cea8d24932fdd17f5a6f57b85223f48558f8bc3a9453e617eb21','38c92e7cd43a75e4849441a0e4a23995a8dd13635cab866e55cbbf21c3b85813'),
(39,'monthly_dues',3,'CREATED',NULL,'{\"member\": \"Jayjay D Mariano\", \"month_covered\": \"2026-11\", \"amount\": \"50.0\", \"payment_method\": \"Salary Deduction\", \"batch_ref\": \"ISU-CAUFA-26-1\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,NULL,'2026-08-07 08:31:07.323777',NULL,'78250954c91bb9332e3376f407cd2330452a92d9c8d1f1ad93bfea5a3b51d1d3','0d193b436be3b80793ae81f17639977691dc25717ae11d1b10d3a407216a2992','2711b2890f8ec2c707ae23f8c1f2bd9f73414753f5e5370ccc67511288bab49d'),
(40,'monthly_dues',4,'CREATED',NULL,'{\"member\": \"Bartholomew Q Badongkadonks\", \"month_covered\": \"2026-11\", \"amount\": \"50.0\", \"payment_method\": \"Salary Deduction\", \"batch_ref\": \"ISU-CAUFA-26-1\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,NULL,'2026-08-07 08:31:07.344457',NULL,'2523dc38e0145088303e56180457a99d4346f61bfd96a0e148f86e9e3c6f8e24','aba7957a7bd8fd83de28c6077797bc630bc8a9e8a0bdb5b59effc5955088a195','78250954c91bb9332e3376f407cd2330452a92d9c8d1f1ad93bfea5a3b51d1d3'),
(41,'monthly_dues',5,'CREATED',NULL,'{\"member\": \"JUSTIN VON T VERGARA\", \"month_covered\": \"2026-11\", \"amount\": \"50.0\", \"payment_method\": \"Salary Deduction\", \"batch_ref\": \"ISU-CAUFA-26-1\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,NULL,'2026-08-07 08:31:07.369535',NULL,'5bb61b6ddf6f61e8d989ff88d86478abd0ef51382f9276b49ca50645b5961164','ac84a32097aff295a87cccffbe51132938c6df532e6643d3d2fa1d0a9a8729bb','2523dc38e0145088303e56180457a99d4346f61bfd96a0e148f86e9e3c6f8e24'),
(42,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:32:04.756128',NULL,'89c45a2e8d021a1069f55dfaa22ce4ad5353e46328746d79eb0e6547c32ccf2d','518d72a0bd5e5f2fe28b0e313a17e5fb68120e463e10ed7b8ea6a16152b4e899','5bb61b6ddf6f61e8d989ff88d86478abd0ef51382f9276b49ca50645b5961164'),
(43,'monthly_dues',5,'VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Reviewed by JAYEM REOJANO','2026-08-07 08:32:13.186115',NULL,'b6d41eb14a97f8db6773319a06d90d0f6661ea207a9e9ace569e960afa2bc28f','c47b856cb2e2ff774285624b183aeb45de047353398e081d094e05df1b1fba9b','89c45a2e8d021a1069f55dfaa22ce4ad5353e46328746d79eb0e6547c32ccf2d'),
(44,'monthly_dues',4,'VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Reviewed by JAYEM REOJANO','2026-08-07 08:32:13.186115',NULL,'dbf3f723482608cd9d5ee6c5cc7fb851f62e85a0fcff26a5508e92476f46ab12','28197d36aafd26f80fd98e40eb6bcb4ff7c00d9607cbfe008e01c4e246476062','b6d41eb14a97f8db6773319a06d90d0f6661ea207a9e9ace569e960afa2bc28f'),
(45,'monthly_dues',3,'VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Reviewed by JAYEM REOJANO','2026-08-07 08:32:13.186115',NULL,'0b0ef845f688da526e0e15187df37dd5093b6cbd025932df6b2ef42c776574d0','2dba48ca72b180e688927e9157cd36feab4e521ec8e874c072aefbb1f317bc43','dbf3f723482608cd9d5ee6c5cc7fb851f62e85a0fcff26a5508e92476f46ab12'),
(46,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:32:13.881587',NULL,'a0a7841ab9c7a576c443e69bc5df181b4d39c43ef7a680aa00140a70ceb69c34','0652337c975261aefc40c592fbc744430932e9a6a23f1ef46c151f8804f15ba7','0b0ef845f688da526e0e15187df37dd5093b6cbd025932df6b2ef42c776574d0'),
(47,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:32:13.963233',NULL,'71fd9d4ef2c97349f3a00e4bc63fd187349b9cb496d48ee63eb7f90415b34a2c','93b7958bb13fb507130e76819f523ae756d51a507fc68a87792a51a0a2a4143f','a0a7841ab9c7a576c443e69bc5df181b4d39c43ef7a680aa00140a70ceb69c34'),
(48,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:32:14.242805',NULL,'09271f9030ff9a579d3ed4c925440bbd5bae279766991978ce3102a2ab74527f','d04d435b105ab2ac96b387e7f1582a6000f3dad3c0f0e4d085e8d38c19f59802','71fd9d4ef2c97349f3a00e4bc63fd187349b9cb496d48ee63eb7f90415b34a2c'),
(49,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:32:14.674172',NULL,'562b2a48f98089ecc0d024f85881237546a5de0a998f85b55c7da9bbe40e671b','b297c0d9e09f41eb23c5ace5f7a3b5b8c2f863affc545ac86366bcc7ae0ac4e2','09271f9030ff9a579d3ed4c925440bbd5bae279766991978ce3102a2ab74527f'),
(50,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:32:15.033862',NULL,'35c003bdf1fcb2e475c132b876fbbdd37a128f7fb840a59b92a36a5366361ee3','bad2c489c0aa826812ec7bc20e169d9dad198a70991070da008e0e8c61886b99','562b2a48f98089ecc0d024f85881237546a5de0a998f85b55c7da9bbe40e671b'),
(51,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:32:15.490325',NULL,'32a40fcbdab8d92225f9f27f9e26b32902423caa799ac876595ca7ff28d87fca','34e4c199645f4fa52c82ece7dad431b00948779090e8a7b4e2dc1106a62f2cca','35c003bdf1fcb2e475c132b876fbbdd37a128f7fb840a59b92a36a5366361ee3'),
(52,'monthly_dues',3,'APPROVED',NULL,NULL,'President',48,'President Account','112.202.44.41',NULL,'qwerty','2026-08-07 08:34:03.617934',NULL,'a62f81d1a9b480379622381073d3ce91dc8fd786bba62e5baae733bc50e9ebae','61a3e824d281bba2192d05a5720cb6e1a4a11d51cf5e2c8caf2ca828f8c5f244','32a40fcbdab8d92225f9f27f9e26b32902423caa799ac876595ca7ff28d87fca'),
(53,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:34:04.306168',NULL,'4597688f65c795b0f65a921f60088fdf081508e70f76d0fa6dfae8caba88664e','4b4889029b6ffa867c8f5e107e3aaf612b0692a00aebf94fe9578a5255d33ee7','a62f81d1a9b480379622381073d3ce91dc8fd786bba62e5baae733bc50e9ebae'),
(54,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:34:04.555802',NULL,'e78fa06d5f2737129ee2c2764aede7b6ec507a4c15888f3c935fcc26f1f6f1e1','d9dda51ac2d6408ba2483d10e9510662584496850ee1a335680d1e4122265aa6','4597688f65c795b0f65a921f60088fdf081508e70f76d0fa6dfae8caba88664e'),
(55,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:34:04.962044',NULL,'c37e80777ac04097f7dad9f59a43a6223d2cf050aa9aa87bff8430f9e65fc1c3','3fa5f3f5896be921b37168149023756f53e8b6e826293b80ee87e69cde5f66fe','e78fa06d5f2737129ee2c2764aede7b6ec507a4c15888f3c935fcc26f1f6f1e1'),
(56,'monthly_dues',4,'APPROVED',NULL,NULL,'President',48,'President Account','112.202.44.41',NULL,NULL,'2026-08-07 08:34:22.328543',NULL,'88bbd2b330159662ba383465a6b04d67ddfdd5c3f0fd434bc43a21376cee2526','498c52124c26181a6f9e338cc9989ddc577faf0e5c5afde0153905a806ca47b7','c37e80777ac04097f7dad9f59a43a6223d2cf050aa9aa87bff8430f9e65fc1c3'),
(57,'monthly_dues',5,'APPROVED',NULL,NULL,'President',48,'President Account','112.202.44.41',NULL,NULL,'2026-08-07 08:34:22.328543',NULL,'1b76d726c3466206e51486be1d6f1d36d1bb7622596884cf4b491512caea908e','724633102428e1dcd0b01c78fe440d608c8b4e0ebe278a4e8c6f25a3a414ed47','88bbd2b330159662ba383465a6b04d67ddfdd5c3f0fd434bc43a21376cee2526'),
(58,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:34:22.928667',NULL,'d642447d7ecf3213b0a0b0d645aeed4cf81246032e8462cd8bab903761a5691f','a474285714a22a4abfbb0680d305017b92a4a46b21885dac38635f56f524cdc9','1b76d726c3466206e51486be1d6f1d36d1bb7622596884cf4b491512caea908e'),
(59,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:34:23.450626',NULL,'e969b6ab3ef02485c027d8616dcc33ea58a01a3d80c67f39a4b08cf9873b561e','7225d4e27473c2867308dab7a4383e8003f95310a715e2fff31107d3ccee8cba','d642447d7ecf3213b0a0b0d645aeed4cf81246032e8462cd8bab903761a5691f'),
(60,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:34:23.888195',NULL,'ffa525d377350a50bf1bdef32db3941143167ed3b29d8063633f9d81e07a9bea','94dccd24054c46d80748052e2192ec2c63ffb5bf1a276bf85b3f9b7f35aaaacf','e969b6ab3ef02485c027d8616dcc33ea58a01a3d80c67f39a4b08cf9873b561e'),
(61,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:34:32.275841',NULL,'33eb964e8200b407bb6d44d9d6afc4b913a603ce7da31deb3ef8f77b420146c1','905588f2cc39e2c6767cbb0f5304cc06bbb40269ddffcf42e261302cba549aa7','ffa525d377350a50bf1bdef32db3941143167ed3b29d8063633f9d81e07a9bea'),
(62,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:34:32.292411',NULL,'a905223d9e35d50aca408f9207f82599819c744a9ee72d974941ca88dc609d31','6cc449963b335c66bcf5f54c6792111d7b48e9ae8ab556e9084b9730c57214ab','ffa525d377350a50bf1bdef32db3941143167ed3b29d8063633f9d81e07a9bea'),
(63,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:37:27.746089',NULL,'5c094b7bf83c9b7374abfb362b4ff9d5977a5eb0ce02b84ed50d74df341928d0','6e6654c8cce48a09ebf52f38880990fb59fa46a074297c994ea19098bd08e773','a905223d9e35d50aca408f9207f82599819c744a9ee72d974941ca88dc609d31'),
(64,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:37:27.810494',NULL,'4659b0c9666d081645b78af9b59b57080e32e13934818351bef4cb5fee9b3b86','72668ce8fbe3027a4a3edebb7e3b41a71834e3b51dc9e966cc84cfb996b5333c','5c094b7bf83c9b7374abfb362b4ff9d5977a5eb0ce02b84ed50d74df341928d0'),
(65,'monthly_dues',6,'CREATED',NULL,'{\"member\": {\"id\": 3, \"name\": \"JUSTIN VON T VERGARA\"}, \"month_covered\": \"2026-12\", \"amount\": \"50\", \"payment_method\": \"Cash OTC\", \"payment_date\": \"2026-08-07\", \"receipt_number\": \"OR-OTC-69911\", \"is_advance\": \"True\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,NULL,'2026-08-07 08:37:35.986308',NULL,'72b08048662262fe50aa4635b412a720223d789673a3089c71f2b847f81bf275','b10965534edda607008f04b2f1d1c673ceb0f13132e8fc8176bb1cbf3a837261','4659b0c9666d081645b78af9b59b57080e32e13934818351bef4cb5fee9b3b86'),
(66,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:37:42.389415',NULL,'b76afb481da2edb94a71749632ca69291707e2aa9e0f73e6be93c85a8da6a35b','ccd4499cb33a738950c086179c7a6d38e6c623ba6acc53449f265fb3fb0302bc','72b08048662262fe50aa4635b412a720223d789673a3089c71f2b847f81bf275'),
(67,'monthly_dues',6,'VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Reviewed by JAYEM REOJANO','2026-08-07 08:37:48.199992',NULL,'fa9acbbc0a376ed57444a5ed4754b51fe434bd24c7407b31635a35635fb717e5','bbf6fad7d2e48cf8ec8d284a7ea7a5b85580f41567b0f442c79900a64b9b71bc','b76afb481da2edb94a71749632ca69291707e2aa9e0f73e6be93c85a8da6a35b'),
(68,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:37:48.777034',NULL,'ee1f00957be451d8ba6a6447405c341bbe9307c14d541943c88dd323a30d5feb','2dab73c3ad6480567f6441476397d5e1fa8fecf5186945dc4a6fa43eaf69123b','fa9acbbc0a376ed57444a5ed4754b51fe434bd24c7407b31635a35635fb717e5'),
(69,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:37:48.900906',NULL,'077f42556faa6a9e47101fc7dd7c093bb63c298aee270e9f7c1217ad40ec010c','9ee27be8db58a19e47a9ab5c4b5321bc721584dc68dbc59335873f53578436f1','ee1f00957be451d8ba6a6447405c341bbe9307c14d541943c88dd323a30d5feb'),
(70,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:37:49.184148',NULL,'ac2d094e68966186d0bb3508f64116630a99353dc3e3725d62c8450d6ed4013f','7f216e51a02262b8a1916b4c6381c66f0ba94235b7b393652d1ecad954befa05','077f42556faa6a9e47101fc7dd7c093bb63c298aee270e9f7c1217ad40ec010c'),
(71,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:37:49.603807',NULL,'991fccec319fa5b3e3efff842b62c13799d1ae86d55c15dfe89f9bcae28a932d','d4e2edd5de934ea29422ca5b7b4c14e76c3b97dc1a74445d4671b841db195c07','ac2d094e68966186d0bb3508f64116630a99353dc3e3725d62c8450d6ed4013f'),
(72,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:37:49.954644',NULL,'7316b3d61876b9caa141c41797ab631dc20fc54a5d53de361b4a37bc52f11bf0','f60238b8ef7038e914c30cf5521b165c48b23a9fb4ff57bdf6e561af8e29f322','991fccec319fa5b3e3efff842b62c13799d1ae86d55c15dfe89f9bcae28a932d'),
(73,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:37:50.317292',NULL,'bdf67ca61437d3469150098726946425a1f782c92f201b91f58f6c53f32a53d4','bfb8e1b17149778389c7539c1b48bb379541c5c6fd0fdd9afc9d40c491231ea4','7316b3d61876b9caa141c41797ab631dc20fc54a5d53de361b4a37bc52f11bf0'),
(74,'monthly_dues',6,'APPROVED',NULL,NULL,'President',48,'President Account','112.202.44.41',NULL,'rrrr','2026-08-07 08:38:27.125690',NULL,'363adeb6ec36bcca94dfaeb04a3f856a4cfcbfe950eb8bda779be894f34e41bf','dc4e690f69ade617b987d290834b6c0ab8f3b06a1ae6f9cec87404f24f3691dc','bdf67ca61437d3469150098726946425a1f782c92f201b91f58f6c53f32a53d4'),
(75,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:38:27.903906',NULL,'53f5a2c563f5db197769536af2f1a8f8e97c3f17c43f43d544725cd66390ccfe','5bd752250e3ed6b6abab00e4ac9aad4e978cf2cfccf674aa57eef4dd9e58f6e2','363adeb6ec36bcca94dfaeb04a3f856a4cfcbfe950eb8bda779be894f34e41bf'),
(76,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:38:28.252383',NULL,'e92ef967c782b4b92e9e42cdb3c06d2bfa8d9b45880aecb386d8881c118f27c0','0db2de54b074943aa9771947eead0ca60e344b1c2f1c4f53acb50e30349826c6','53f5a2c563f5db197769536af2f1a8f8e97c3f17c43f43d544725cd66390ccfe'),
(77,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:38:28.633676',NULL,'0b3260511c5fe13f8b0958d080937add61769e696e4a7008b1822d200f6b9014','4197a46cd56bc6a9efcbfc221fde3b0fc6d7daf8bd9ab4541c0998e1322258ed','e92ef967c782b4b92e9e42cdb3c06d2bfa8d9b45880aecb386d8881c118f27c0'),
(78,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:38:34.884254',NULL,'a4856d7c3f207ee5521c33eebff781680c9f2457a9282f6a33b347a09a3b0617','56a7b27578135afa8ec3008c348c8e455b20a8cd0121689e0891b54d5f507ea1','0b3260511c5fe13f8b0958d080937add61769e696e4a7008b1822d200f6b9014'),
(79,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:38:34.917956',NULL,'78edf22b00c57a3b3c8b13c375c5355dac4edae180172c44df765257fc87da4c','a5f7353f89c5dfb59ecb4be19473ca40b96e8c5fd8fd2e194c0c7cb04f7ccfd5','a4856d7c3f207ee5521c33eebff781680c9f2457a9282f6a33b347a09a3b0617'),
(80,'medical_aid',0,'READ',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Auditor viewed pending medical aid list (1 records)','2026-08-07 08:41:04.683467',NULL,'afaf6b3d7784c57da29890e52e60ddff4639123eb95ee5283fcb30e4868d2b87','329ce2b59c586d6c9f649f3f65d407e86a3c5f19f2adec3b2b01afb6c16cba07','78edf22b00c57a3b3c8b13c375c5355dac4edae180172c44df765257fc87da4c'),
(81,'medical_aid',1,'VERIFIED',NULL,NULL,'Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Reviewed by JAYEM REOJANO','2026-08-07 08:41:16.977492',NULL,'4e8bfa63d0111437f9f58662d324ef73f4103d1fb446600ed1ecef9ea5762189','d0550a4df283648da642659ea9a4f7b50aaae858d6ff28a111167a2a0ff58b29','afaf6b3d7784c57da29890e52e60ddff4639123eb95ee5283fcb30e4868d2b87'),
(82,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:41:17.710369',NULL,'d5863faf63ccde5bc4e6cb45568e59ce624cf24e2392d3bace6a3bec11202715','9125b5e95d6fc088a74ed4586f49ecbddc166280df5ed19ad749987db720759e','4e8bfa63d0111437f9f58662d324ef73f4103d1fb446600ed1ecef9ea5762189'),
(83,'medical_aid',0,'READ',NULL,NULL,'President',48,'President Account','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','President viewed auditor-approved medical aid queue (1 records)','2026-08-07 08:41:28.651798',NULL,'c7561c983789fcd60672fe053f38d4d0b205140aac4122e38788ff1569eeb531','b5d22ce757bdc2fa1e2de6961c572e69bae391e2257044e62657dc084b02d74f','d5863faf63ccde5bc4e6cb45568e59ce624cf24e2392d3bace6a3bec11202715'),
(84,'medical_aid',0,'READ',NULL,NULL,'President',48,'President Account','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','President viewed auditor-approved medical aid queue (1 records)','2026-08-07 08:41:28.669294',NULL,'2ef039a3b0210cd485c660272667f2ef714b132f8ae319b41d54b952b27528cb','97b7f78cacfd0923ef196b8b9ba628db22ef3fa772ac176d3413e39b3a5a6901','d5863faf63ccde5bc4e6cb45568e59ce624cf24e2392d3bace6a3bec11202715'),
(85,'medical_aid',0,'READ',NULL,NULL,'President',48,'President Account','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','President viewed auditor-approved medical aid queue (1 records)','2026-08-07 08:45:01.596495',NULL,'fa7486f09510cdf05712fc0814206ac8fbcb6f2c4c877e4adabaf50867061ec3','7de6b79696654babcda7e10fbc9e17e93baf6119863f0977154b74bb4eab7c25','2ef039a3b0210cd485c660272667f2ef714b132f8ae319b41d54b952b27528cb'),
(86,'medical_aid',0,'READ',NULL,NULL,'President',48,'President Account','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','President viewed auditor-approved medical aid queue (1 records)','2026-08-07 08:45:01.604574',NULL,'477e395be05a94f642e1a631616ff319cf027c794040813e80e6cf2158c9d178','4c82e639f4ac9d42acb97826cb29fa86f894394b0bf9b41c3832660b15344c68','0000000000000000000000000000000000000000000000000000000000000000'),
(87,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:45:04.497945',NULL,'1b64b5b569aa61c013a13a8632dc3d813b9dc0a1a194258b22007f16395543f2','ec5dd5566fdb5ac1644443a5262bb1b7e4e22b354480c3b42568d01f394b6fff','477e395be05a94f642e1a631616ff319cf027c794040813e80e6cf2158c9d178'),
(88,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:45:04.519482',NULL,'c6b407fd33d4013cca3d9a71bb458e6d92680d01e9c86e2039bb8daa7287dfa2','7eefc72dd10f6a74f53e5bccf9d62a5c3eba54d643f62527dc014a583cd360d2','477e395be05a94f642e1a631616ff319cf027c794040813e80e6cf2158c9d178'),
(89,'medical_aid',0,'READ',NULL,NULL,'President',48,'President Account','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','President viewed auditor-approved medical aid queue (1 records)','2026-08-07 08:50:55.889061',NULL,'8d15a91639788da526aef00f40c389182ee3018d7cff3b1bd3529ae29a720706','287f1bf80cd979efaa82cfe7579b6c517963b813780f9afc5d3f64ac6d58dd45','c6b407fd33d4013cca3d9a71bb458e6d92680d01e9c86e2039bb8daa7287dfa2'),
(90,'medical_aid',0,'READ',NULL,NULL,'President',48,'President Account','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','President viewed auditor-approved medical aid queue (1 records)','2026-08-07 08:50:56.355114',NULL,'a29c1a4d29c9a2301295e8632dcbad9e90bcc745e254b832fed31709247cf755','402e99c234718ff8ecf6d27723eb9e587d86e02d931b1a3ad6910e257fed8f0a','8d15a91639788da526aef00f40c389182ee3018d7cff3b1bd3529ae29a720706'),
(91,'medical_aid',1,'APPROVED',NULL,'{\"president_decision\": \"Approved\", \"approved_amount\": \"20000.0\", \"action\": \"Presidential Approved\"}','President',48,'President Account','112.202.44.41',NULL,'PALDO','2026-08-07 08:54:05.117843',NULL,'e96dddd69f984ad4a55aded0e1539cbdf4c817dfbd1525ae475ba36377c05854','8e03dfc926465e48afadc107286da42581311de9a74e6b2dca810ca3bf4bc03b','a29c1a4d29c9a2301295e8632dcbad9e90bcc745e254b832fed31709247cf755'),
(92,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 08:55:29.844662',NULL,'7539a7d08169f1133c709819d32f221a758a6abf8b3c9261cb658bb2b89a181d','ee09c30a83f2decfa181385441e0204d3c336f9ced9877f276df7f704761a569','e96dddd69f984ad4a55aded0e1539cbdf4c817dfbd1525ae475ba36377c05854'),
(93,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 08:55:29.862302',NULL,'70f66fb7cdc90b6a04f0bd62b49933d259d450e0ccbaff449afe051d8369626f','8aa17775aef2e649fc30b55da2daee50d296ebf511b179974abe0cb71486e1da','e96dddd69f984ad4a55aded0e1539cbdf4c817dfbd1525ae475ba36377c05854'),
(94,'contribution',1,'PAYMENT_RECORDED',NULL,'{\"status\": \"RECORDED\", \"paid_amount\": \"10000.00\", \"payment_date\": \"2026-08-07\", \"aid_tracking_post_id\": \"1\", \"member_id\": \"2\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Contribution payment recorded.','2026-08-07 08:58:54.512517',NULL,'5c9abca63d8e04e41a248410a45eff05868e442eec5288ee7bcb947bc46a935f','005e48f115e286b3c57629671d158ef92e84c3585f78ff8bccb46d82afdbb672','70f66fb7cdc90b6a04f0bd62b49933d259d450e0ccbaff449afe051d8369626f'),
(95,'contribution',2,'PAYMENT_RECORDED',NULL,'{\"status\": \"RECORDED\", \"paid_amount\": \"10000.00\", \"payment_date\": \"2026-08-07\", \"aid_tracking_post_id\": \"1\", \"member_id\": \"3\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Contribution payment recorded.','2026-08-07 08:58:54.646930',NULL,'5756845b81655d6d0923135b06934f17d1d15c15e2856834afb30ad6a0e58dcd','0b5fc830f5ba92413a3d7be0443858b2fa947cc4cbd2ac9dc3ab7087238fdc97','5c9abca63d8e04e41a248410a45eff05868e442eec5288ee7bcb947bc46a935f'),
(96,'AID_TRACKING_POST',1,'DEDUCTION_SHEET_UPLOADED',NULL,'{\"batch_reference\": \"PAY-2026\", \"payroll_period\": \"2026-07\", \"file_name\": \"IMG_20260806_070856.jpg\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Deduction sheet uploaded for post 1: ref PAY-2026, period 2026-07','2026-08-07 09:01:29.811033',NULL,'8a955c6e65543af688fa864944ce23a1d1f0ec7826ceffd82a6cac700e6b7904','3eee051dbc2416285a46b0f199e5488eb25d10420595fbc41001b72e48192a23','5756845b81655d6d0923135b06934f17d1d15c15e2856834afb30ad6a0e58dcd'),
(97,'AID_TRACKING_POST',1,'DEDUCTION_REMITTANCE_RECORDED',NULL,'{\"remitted_amount\": \"20000\", \"remittance_reference\": \"BPI-69\", \"remitted_date\": \"2026-08-07\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Remittance recorded — ref BPI-69, amount 20000, date 2026-08-07','2026-08-07 09:01:45.566945',NULL,'853e5855dac4c0a2068154f9cfb09458133425f74289ccbe791db43f78762f47','576ff6a8160f63d61a901b7a19fc2fb78c910392631c0e387a84a97138bb7b3b','8a955c6e65543af688fa864944ce23a1d1f0ec7826ceffd82a6cac700e6b7904'),
(98,'contribution',1,'PAYMENT_RECORDED',NULL,'{\"status\": \"RECORDED\", \"paid_amount\": \"10000.00\", \"payment_date\": \"2026-08-07\", \"aid_tracking_post_id\": \"1\", \"member_id\": \"2\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Contribution payment recorded.','2026-08-07 09:01:52.951189',NULL,'bb1a60cf91438143ba290d9d3f2cf84e98300b7696266c9e53b760bf5d27f694','f20bce73a848d4b3165b0f3bdbf34a634be342c2d875ff4b877d0e69c37fef64','853e5855dac4c0a2068154f9cfb09458133425f74289ccbe791db43f78762f47'),
(99,'contribution',2,'PAYMENT_RECORDED',NULL,'{\"status\": \"RECORDED\", \"paid_amount\": \"10000.00\", \"payment_date\": \"2026-08-07\", \"aid_tracking_post_id\": \"1\", \"member_id\": \"3\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Contribution payment recorded.','2026-08-07 09:01:52.955368',NULL,'cf152b2633fb23748d98da2b920b7b9b55a285615166d858463eadd84b23032f','268a7a6c342e7060285f9af04e7e404548b4a4a040a0433519c01e3a529958ed','bb1a60cf91438143ba290d9d3f2cf84e98300b7696266c9e53b760bf5d27f694'),
(100,'AID_TRACKING_POST',1,'FINISH_REQUESTED',NULL,'{\"finish_status\": \"pending_auditor\", \"finish_skip_remaining\": \"True\", \"paid_ratio\": \"2/2\", \"deduction_batch_reference\": \"PAY-2026\", \"deduction_payroll_period\": \"2026-07\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Finish requested with deduction ref PAY-2026 for period 2026-07','2026-08-07 09:02:01.210968',NULL,'24b5c85bec2758db8679765a1003aaf632b178299c44b4f393ce95c1453c1050','ca64361802d9c6222a3c1383941e8931f9a483669eef420baff00590cff8d591','cf152b2633fb23748d98da2b920b7b9b55a285615166d858463eadd84b23032f'),
(101,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 09:02:01.389089',NULL,'0f201ecc338c2a923448a6e0501c6f6ea3014b0dcb19fc379f2875efb3606ac5','2dcdc5c8aa8a77ab07b3040c8d364a88b5a86164231161fd0440e93737b94c76','24b5c85bec2758db8679765a1003aaf632b178299c44b4f393ce95c1453c1050'),
(102,'AID_TRACKING_POST',1,'FINISH_VERIFIED',NULL,'{\"deduction_batch_reference\": \"PAY-2026\", \"deduction_payroll_period\": \"2026-07\", \"paid_count\": \"2\", \"inflow_count\": \"2\"}','Auditor',50,'JAYEM REOJANO','111.90.232.145',NULL,'Auditor verified finish — ref PAY-2026, period 2026-07','2026-08-07 09:07:47.120226',NULL,'db2798bfbda64ec825346dc2a63e6c707358497d8ad6705db37c5e7fb3a8d1de','673176958662125d8cee0fd1448101773aeac2dd0d57e546786673dc6a5a31de','0f201ecc338c2a923448a6e0501c6f6ea3014b0dcb19fc379f2875efb3606ac5'),
(103,'AID_TRACKING_POST',1,'FINISH_APPROVED',NULL,'{\"finish_status\": \"pending_release\", \"deduction_batch_reference\": \"PAY-2026\", \"deduction_payroll_period\": \"2026-07\"}','President',48,'President Account','112.202.44.41',NULL,'Finish approved (pending release) — deduction ref PAY-2026, period 2026-07','2026-08-07 09:09:22.350172',NULL,'e62b5f76c4c581b3b7e7c7f09538f83fe66608c1dce14ade73a04703abf54603','1ff85e86012353addbe18d1f669a5fe53094f4e2e7005e27563727bcd200d48c','db2798bfbda64ec825346dc2a63e6c707358497d8ad6705db37c5e7fb3a8d1de'),
(104,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 09:10:02.897886',NULL,'d945c2970febfb3d9371bed211e85be6db5e0f8cced7ca4ea3817a6d129b0da6','5c9d92553e66dfcd753e9c24d598954cf7e82a7622f526070fac5738fa54b1e5','e62b5f76c4c581b3b7e7c7f09538f83fe66608c1dce14ade73a04703abf54603'),
(105,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 09:10:02.903380',NULL,'91db6dc3456f52f84583ade7cb44c6e159079277d23e040fe9a11658f78c3c9c','baeda987053ec97da3b2fb3097900642e45a1550bd35cdd46faa316e4d494485','e62b5f76c4c581b3b7e7c7f09538f83fe66608c1dce14ade73a04703abf54603'),
(106,'AID_TRACKING_POST',1,'FINISH_RELEASED',NULL,'{\"finish_status\": \"approved\", \"is_active\": \"False\", \"inflow_count\": \"0\", \"outflow_count\": \"1\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,NULL,'2026-08-07 09:12:01.008326',NULL,'e8f908b163320f75fe825fc4ccd3cdfa6814b3e41194398debe1d3d242c70be5','7be9522482e3ebe819bfbe7bef39ebb38b8f8b9ddd718455c0c6d9a0b77ded7d','91db6dc3456f52f84583ade7cb44c6e159079277d23e040fe9a11658f78c3c9c'),
(107,'AID_TRACKING_POST',1,'RELEASE_NOTIFIED',NULL,'{\"total_collected\": \"20000.0\", \"total_members\": \"2\", \"paid_count\": \"2\", \"skipped_count\": \"0\"}','Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145',NULL,'Release completed — Medical Aid for Jayjay D Mariano. ₱20000.00 from 2/2 members. Released by BEN HAMMAD GUDANI','2026-08-07 09:12:01.023537',NULL,'ef0f953e88a7714fe83ac6790b5a9f59f47ae57eca9d16484a494edce84ab2c3','8070839a816dce872539a38156922f87a03a01f28dba3f5ab61b9bbe04a65e0c','e8f908b163320f75fe825fc4ccd3cdfa6814b3e41194398debe1d3d242c70be5'),
(108,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 09:12:14.631156',NULL,'a55ce4e168cd54bae9ffffcf7a06b390de860b0a05c39bdebd8e5c44ddd88eee','b4b88051dfd0d3c3c5fc7475d9a3b0a256d6c8a75e7594579d7f80d827993315','ef0f953e88a7714fe83ac6790b5a9f59f47ae57eca9d16484a494edce84ab2c3'),
(109,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 09:12:14.640576',NULL,'cdb1cbf7b75a911a6e988afcd9aa1da6a8139568627a377853a538e0abcbd585','9c31392a517a48f2ec150926f8f652c53bcdcfa0beeb9f84c607d6583678f5ef','0000000000000000000000000000000000000000000000000000000000000000'),
(110,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 09:15:45.220589',NULL,'0b22eac1a2f4e733a5f1d191c8ce9542fafbcacb4e743656998826858678336e','a09ad3377af1ea99374f1861d4983c2cae7432fc3ffa447a0e96f3b5e9078fe0','cdb1cbf7b75a911a6e988afcd9aa1da6a8139568627a377853a538e0abcbd585'),
(111,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 09:15:45.230839',NULL,'0881b32c94e823b64174da24cf7761c47647b7d05ad5861fce254886aa3fc3f3','b230d66b8d4852b3b6ecae57a00d2ab61be1fb2fa818c6df65c1cd940ed7fde4','0b22eac1a2f4e733a5f1d191c8ce9542fafbcacb4e743656998826858678336e'),
(112,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed medical aid list (1 records)','2026-08-07 09:16:21.830112',NULL,'6e270e775b52bfa7c6a1f26a9e578bf047871ac3574d49eb72455dc985ac6ae7','47a3c10453ba7dd9adc45e2b052ee69e22dd5341c2d6fc3133ef04ea8b3af47d','0881b32c94e823b64174da24cf7761c47647b7d05ad5861fce254886aa3fc3f3'),
(113,'medical_aid',0,'READ',NULL,NULL,'Treasurer',49,'BEN HAMMAD GUDANI','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Treasurer viewed returned medical aid list (0 records)','2026-08-07 09:16:21.945557',NULL,'51fa91b431a7883b5085378123e1286a44317ae715e2614cffd7ed0a3061f012','d0e8e0573c502a11f7a1e9a5d71bc3fc738f4a6930182262ff784df8da628a73','6e270e775b52bfa7c6a1f26a9e578bf047871ac3574d49eb72455dc985ac6ae7');

/*Table structure for table `hero_slide` */

DROP TABLE IF EXISTS `hero_slide`;

CREATE TABLE `hero_slide` (
  `hero_id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `subtitle` longtext NOT NULL,
  `image` varchar(100) DEFAULT NULL,
  `button_text` varchar(50) NOT NULL,
  `button_url` varchar(500) NOT NULL,
  `sort_order` int(11) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`hero_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `hero_slide` */

/*Table structure for table `login_attempt_log` */

DROP TABLE IF EXISTS `login_attempt_log`;

CREATE TABLE `login_attempt_log` (
  `attempt_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `username_used` varchar(150) NOT NULL,
  `ip_address` char(39) NOT NULL,
  `device_info` varchar(255) DEFAULT NULL,
  `result` varchar(50) NOT NULL,
  `attempted_at` datetime(6) NOT NULL,
  `user_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`attempt_id_PK`),
  KEY `LOGIN_ATTEMPT_LOG_user_id_FK_3d7e6e0a_fk_OFFICER_USER_user_id_PK` (`user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `login_attempt_log` */

insert  into `login_attempt_log`(`attempt_id_PK`,`username_used`,`ip_address`,`device_info`,`result`,`attempted_at`,`user_id_FK`) values 
(1,'treasurer','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','MFA_REQUIRED','2026-08-07 08:05:33.942829',49),
(2,'treasurer','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Success','2026-08-07 08:06:04.997118',49),
(3,'23-232323','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (Linux; Android 15; CPH2591 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/573.0.0.44.88;]','account_not_found','2026-08-07 08:08:10.907986',NULL),
(4,'142joe','112.202.44.41','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','incorrect_password','2026-08-07 08:08:24.665556',96),
(5,'142joe','112.202.44.41','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','incorrect_password','2026-08-07 08:08:35.378895',96),
(6,'142joe','112.202.44.41','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','incorrect_password','2026-08-07 08:08:47.709245',96),
(7,'21-232323','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (Linux; Android 15; CPH2591 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/573.0.0.44.88;]','incorrect_password','2026-08-07 08:08:56.575253',94),
(8,'bart','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','Success','2026-08-07 08:09:02.485613',95),
(9,'21-232323','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (Linux; Android 15; CPH2591 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/573.0.0.44.88;]','Success','2026-08-07 08:09:18.467702',94),
(10,'142joe','112.202.44.41','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36','Success','2026-08-07 08:09:25.848151',96),
(11,'bart','111.90.232.145','Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Edg/151.0.0.0 Mobile Safari/537.36','incorrect_password','2026-08-07 08:13:01.742636',95),
(12,'bart','111.90.232.145','Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Edg/151.0.0.0 Mobile Safari/537.36','Success','2026-08-07 08:14:03.902291',95),
(13,'bart','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0','Success','2026-08-07 08:15:28.055155',95),
(14,'auditor','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','MFA_REQUIRED','2026-08-07 08:31:37.291957',50),
(15,'auditor','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Success','2026-08-07 08:32:02.782849',50),
(16,'president','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','incorrect_password','2026-08-07 08:32:34.509628',48),
(17,'president','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','MFA_REQUIRED','2026-08-07 08:32:42.657925',48),
(18,'president','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','Success','2026-08-07 08:33:05.935755',48),
(19,'treasurer','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','MFA_REQUIRED','2026-08-07 08:36:58.348816',49),
(20,'treasurer','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Success','2026-08-07 08:37:24.187798',49),
(21,'21-232323','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36','incorrect_password','2026-08-07 08:51:59.686421',94),
(22,'21-231323','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36','account_not_found','2026-08-07 08:52:21.421058',NULL),
(23,'21-232323','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36','Success','2026-08-07 08:52:50.176662',94),
(24,'auditor','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','MFA_REQUIRED','2026-08-07 09:02:31.091910',50),
(25,'auditor','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Success','2026-08-07 09:02:53.749019',50),
(26,'president','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','MFA_REQUIRED','2026-08-07 09:05:27.235214',48),
(27,'president','112.202.44.41','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36','Success','2026-08-07 09:08:20.956627',48),
(28,'treasurer','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','MFA_REQUIRED','2026-08-07 09:09:38.669971',49),
(29,'treasurer','111.90.232.145','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0','Success','2026-08-07 09:10:00.352304',49);

/*Table structure for table `medical_aid` */

DROP TABLE IF EXISTS `medical_aid`;

CREATE TABLE `medical_aid` (
  `medical_aid_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `request_date` date NOT NULL,
  `hospital_bill_amount` decimal(10,2) NOT NULL,
  `claim_year` int(11) NOT NULL,
  `document_status` varchar(50) NOT NULL,
  `policy_record_status` varchar(50) NOT NULL,
  `validated_aid_amount` decimal(10,2) NOT NULL,
  `status` varchar(50) NOT NULL,
  `president_decision` varchar(50) DEFAULT NULL,
  `release_reference` varchar(100) DEFAULT NULL,
  `acknowledgement_reference` varchar(100) DEFAULT NULL,
  `member_id_FK` int(11) NOT NULL,
  `auditor_verified_by_user_id_FK` int(11) DEFAULT NULL,
  `president_decided_by_user_id_FK` int(11) DEFAULT NULL,
  `released_by_user_id_FK` int(11) DEFAULT NULL,
  `treasurer_validated_by_user_id_FK` int(11) DEFAULT NULL,
  `requested_amount` decimal(10,2) DEFAULT NULL,
  `hospital_name` varchar(255) NOT NULL,
  `hospital_date` varchar(50) DEFAULT NULL,
  `disbursement_source` varchar(20) DEFAULT NULL,
  `admission_date` date DEFAULT NULL,
  `discharge_date` date DEFAULT NULL,
  `hospital_address` varchar(500) DEFAULT NULL,
  `reason_for_request` longtext DEFAULT NULL,
  PRIMARY KEY (`medical_aid_id_PK`),
  KEY `MEDICAL_AID_member_id_FK_a3f6c869_fk_MEMBER_member_id_PK` (`member_id_FK`),
  KEY `MEDICAL_AID_auditor_verified_by__d16afda1_fk_OFFICER_U` (`auditor_verified_by_user_id_FK`),
  KEY `MEDICAL_AID_president_decided_by_8781c5c8_fk_OFFICER_U` (`president_decided_by_user_id_FK`),
  KEY `MEDICAL_AID_treasurer_validated__621f73b2_fk_OFFICER_U` (`treasurer_validated_by_user_id_FK`),
  KEY `MEDICAL_AID_released_by_user_id_FK_77cb71e1` (`released_by_user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `medical_aid` */

insert  into `medical_aid`(`medical_aid_id_PK`,`request_date`,`hospital_bill_amount`,`claim_year`,`document_status`,`policy_record_status`,`validated_aid_amount`,`status`,`president_decision`,`release_reference`,`acknowledgement_reference`,`member_id_FK`,`auditor_verified_by_user_id_FK`,`president_decided_by_user_id_FK`,`released_by_user_id_FK`,`treasurer_validated_by_user_id_FK`,`requested_amount`,`hospital_name`,`hospital_date`,`disbursement_source`,`admission_date`,`discharge_date`,`hospital_address`,`reason_for_request`) values 
(1,'2026-08-07',20000.00,2026,'Pending','Pending',20000.00,'Released','Approved',NULL,NULL,1,NULL,48,NULL,49,20000.00,'ISU Family',NULL,NULL,'2026-08-03','2026-08-31','Ajdjdjs','Wheksj');

/*Table structure for table `member` */

DROP TABLE IF EXISTS `member`;

CREATE TABLE `member` (
  `member_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `contact_number` varchar(50) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `employment_status` varchar(50) NOT NULL,
  `membership_status` varchar(50) NOT NULL,
  `member_type` varchar(50) NOT NULL,
  `date_joined` date NOT NULL,
  `department` varchar(100) DEFAULT NULL,
  `employee_id` varchar(50) DEFAULT NULL,
  `position` varchar(100) DEFAULT NULL,
  `department_id_FK` int(11) DEFAULT NULL,
  `officer_user_id_FK` int(11) DEFAULT NULL,
  `profile_picture` varchar(100) DEFAULT NULL,
  `pin_code` varchar(255) DEFAULT NULL,
  `qr_code` varchar(100) DEFAULT NULL,
  `emergency_contact` varchar(255) DEFAULT NULL,
  `emergency_number` varchar(50) DEFAULT NULL,
  `setup_complete` tinyint(1) NOT NULL,
  `qr_data` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`member_id_PK`),
  UNIQUE KEY `MEMBER_employee_id_6c5f9503_uniq` (`employee_id`),
  KEY `MEMBER_department_id_FK_4098768a_fk_DEPARTMENT_department_id_PK` (`department_id_FK`),
  KEY `MEMBER_officer_user_id_FK_884d61d4_fk_OFFICER_USER_user_id_PK` (`officer_user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `member` */

insert  into `member`(`member_id_PK`,`full_name`,`contact_number`,`email`,`employment_status`,`membership_status`,`member_type`,`date_joined`,`department`,`employee_id`,`position`,`department_id_FK`,`officer_user_id_FK`,`profile_picture`,`pin_code`,`qr_code`,`emergency_contact`,`emergency_number`,`setup_complete`,`qr_data`) values 
(1,'Jayjay D Mariano','09123456789','jasminerotugal@gmail.com','Active','Permanent','Member','2026-08-07','CCSICT','21-232323','Assistant Professor',NULL,94,'profile_pics/inbound1036653931681477155.jpg','pin_pbkdf2_sha256$200000$bc830294d7028fdfb6d48ece46299518$7fcdafa00e5d2623986aa95f46940f24623b826058ef364caccb98f59e334ad1','qr_codes/inbound2635693795080452425.png','Keifer Watson','09786453214',1,'ISU-2RPFHCI'),
(2,'Bartholomew Q Badongkadonks','09182367127','yegan.kiru@gmail.com','Active','Permanent','Member','2026-08-07','CCSICT','bart','PROF 1',NULL,95,'profile_pics/IMG_20260806_070856.jpg','pin_pbkdf2_sha256$200000$b725541919adff0b0ad3d11d3904052b$8044877660029eae5f9fc721fc19d6a09e8385b0db055746c7107bbb7c0609e7','qr_codes/46e5a016-68dc-4c43-9d26-ea0a42442e82_bO5gpdu.jpg','Lebron James','09123612746',1,'ISU-MMXSUUZ'),
(3,'JUSTIN VON T VERGARA','77777777777','justinvon.vergara_cyn@isu.edu.ph','Active','Permanent','Member','2026-08-07','CCSICT','142joe','ASSISTANT PROFESSOR 1',NULL,96,'profile_pics/3431_FinkUun.jpg','pin_pbkdf2_sha256$200000$2a348f3ebe9d9045830fe26a419ac4d2$0538b543f96fbe1460835ab48a6c53db789996473fdba0027494c27252922c7b','qr_codes/3162_63Ca8Dg.png','EFIPANIO S VERGARA JR','12345678912',1,'ISU-BUJKID4');

/*Table structure for table `member_ledger` */

DROP TABLE IF EXISTS `member_ledger`;

CREATE TABLE `member_ledger` (
  `ledger_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `transaction_type` varchar(50) NOT NULL,
  `amount` decimal(12,2) NOT NULL,
  `direction` varchar(10) NOT NULL,
  `balance_after` decimal(12,2) NOT NULL,
  `reference_id` int(11) DEFAULT NULL,
  `reference_type` varchar(50) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `notes` longtext DEFAULT NULL,
  `recorded_at` datetime(6) NOT NULL,
  `member_id_FK` int(11) NOT NULL,
  `recorded_by_user_id_FK` int(11) NOT NULL,
  PRIMARY KEY (`ledger_id_PK`),
  KEY `MEMBER_LEDGER_recorded_by_user_id__ea4dfc59_fk_OFFICER_U` (`recorded_by_user_id_FK`),
  KEY `MEMBER_LEDG_member__9bc074_idx` (`member_id_FK`),
  KEY `MEMBER_LEDG_transac_4c41b6_idx` (`transaction_type`),
  KEY `MEMBER_LEDG_recorde_fa4ecd_idx` (`recorded_at`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `member_ledger` */

insert  into `member_ledger`(`ledger_id_PK`,`transaction_type`,`amount`,`direction`,`balance_after`,`reference_id`,`reference_type`,`description`,`notes`,`recorded_at`,`member_id_FK`,`recorded_by_user_id_FK`) values 
(1,'membership_fee',100.00,'credit',100.00,1,'MembershipFee','Membership Fee Payment',NULL,'2026-08-07 08:07:24.887681',1,48),
(2,'membership_fee',100.00,'credit',100.00,2,'MembershipFee','Membership Fee Payment',NULL,'2026-08-07 08:07:30.402621',2,48),
(3,'membership_fee',100.00,'credit',100.00,3,'MembershipFee','Membership Fee Payment',NULL,'2026-08-07 08:07:36.672853',3,48),
(4,'monthly_dues',50.00,'credit',150.00,2,'MonthlyDues','Monthly Dues Payment - 2026-10',NULL,'2026-08-07 08:26:13.603083',1,48),
(5,'monthly_dues',50.00,'credit',200.00,1,'MonthlyDues','Monthly Dues Payment - 2026-09',NULL,'2026-08-07 08:26:29.698505',1,48),
(6,'monthly_dues',50.00,'credit',250.00,3,'MonthlyDues','Monthly Dues Payment - 2026-11',NULL,'2026-08-07 08:33:57.171275',1,48),
(7,'monthly_dues',50.00,'credit',150.00,4,'MonthlyDues','Monthly Dues Payment - 2026-11',NULL,'2026-08-07 08:34:10.320593',2,48),
(8,'monthly_dues',50.00,'credit',150.00,5,'MonthlyDues','Monthly Dues Payment - 2026-11',NULL,'2026-08-07 08:34:16.304385',3,48),
(9,'monthly_dues',50.00,'credit',200.00,6,'MonthlyDues','Monthly Dues Payment - 2026-12',NULL,'2026-08-07 08:38:21.034159',3,48);

/*Table structure for table `member_registration_request` */

DROP TABLE IF EXISTS `member_registration_request`;

CREATE TABLE `member_registration_request` (
  `request_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `employee_id` varchar(50) NOT NULL,
  `email` varchar(255) DEFAULT NULL,
  `department` varchar(100) DEFAULT NULL,
  `position` varchar(100) DEFAULT NULL,
  `membership_category` varchar(50) NOT NULL,
  `payment_method` varchar(50) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `receipt_number` varchar(100) NOT NULL,
  `reference_number` varchar(100) DEFAULT NULL,
  `payment_date` date DEFAULT NULL,
  `status` varchar(50) NOT NULL,
  `returned_reason` longtext DEFAULT NULL,
  `submitted_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `submitted_by_ip` char(39) DEFAULT NULL,
  `submitted_by_user_agent` varchar(255) DEFAULT NULL,
  `processed_by_user_id_FK` int(11) DEFAULT NULL,
  `password_hash` varchar(255) DEFAULT NULL,
  `auditor_verified_by_user_id_FK` int(11) DEFAULT NULL,
  `president_approved_by_user_id_FK` int(11) DEFAULT NULL,
  `treasurer_verified_by_user_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`request_id_PK`),
  KEY `MEMBER_REGISTRATION__auditor_verified_by__fd89364e_fk_OFFICER_U` (`auditor_verified_by_user_id_FK`),
  KEY `MEMBER_REGISTRATION__president_approved_b_8619f09f_fk_OFFICER_U` (`president_approved_by_user_id_FK`),
  KEY `MEMBER_REGISTRATION__treasurer_verified_b_a88205c4_fk_OFFICER_U` (`treasurer_verified_by_user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `member_registration_request` */

insert  into `member_registration_request`(`request_id_PK`,`full_name`,`employee_id`,`email`,`department`,`position`,`membership_category`,`payment_method`,`amount`,`receipt_number`,`reference_number`,`payment_date`,`status`,`returned_reason`,`submitted_at`,`updated_at`,`submitted_by_ip`,`submitted_by_user_agent`,`processed_by_user_id_FK`,`password_hash`,`auditor_verified_by_user_id_FK`,`president_approved_by_user_id_FK`,`treasurer_verified_by_user_id_FK`) values 
(1,'JUSTIN VON T VERGARA','142joe','justinvon.vergara_cyn@isu.edu.ph','CCSICT','ASSISTANT PROFESSOR 1','Permanent','GCash',100.00,'REG-20260807080539-142joe',NULL,'2026-08-07','President Approved',NULL,'2026-08-07 08:05:39.688068','2026-08-07 08:07:36.677231','112.202.44.41','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36',49,'24c3f84d455824ed7edcf9130cfc2e5560f5a94596531b160ad0d44c33aaa73a',50,48,49),
(2,'Jayjay D Mariano','21-232323','jasminerotugal@gmail.com','CCSICT','Assistant Professor','Permanent','OTC Cash',100.00,'REG-20260807080546-21-232323',NULL,'2026-08-31','President Approved',NULL,'2026-08-07 08:05:46.477891','2026-08-07 08:07:25.871788','2405:8d40:4804:6e0c:4780:f302:3845:799e','Mozilla/5.0 (Linux; Android 15; CPH2591 Build/AP3A.240617.008; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.181 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/573.0.0.44.88;]',49,'886533ae956168bc8b07e43e6da167474d228d230026e2e2630e2458ae11b5b3',50,48,49),
(3,'Bartholomew Q Badongkadonks','bart','yegan.kiru@gmail.com','CCSICT','PROF 1','Permanent','Bank Transfer',100.00,'REG-20260807080552-bart',NULL,'2026-08-07','President Approved',NULL,'2026-08-07 08:05:52.483936','2026-08-07 08:07:30.430236','111.90.232.145','Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 EdgA/142.0.0.0',49,'211514260ae1501ed66086fae0aa1204448026684396bae75f580d2fd1449cfc',50,48,49);

/*Table structure for table `membership_fee` */

DROP TABLE IF EXISTS `membership_fee`;

CREATE TABLE `membership_fee` (
  `fee_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `amount` decimal(10,2) NOT NULL,
  `payment_date` date NOT NULL,
  `payment_status` varchar(50) NOT NULL,
  `receipt_number` varchar(100) DEFAULT NULL,
  `deposit_reference` varchar(100) DEFAULT NULL,
  `member_id_FK` int(11) NOT NULL,
  `recorded_by_user_id_FK` int(11) NOT NULL,
  `payment_method` varchar(50) NOT NULL,
  PRIMARY KEY (`fee_id_PK`),
  UNIQUE KEY `MEMBERSHIP_FEE_member_id_FK_receipt_number_fa8cb308_uniq` (`member_id_FK`,`receipt_number`),
  KEY `MEMBERSHIP_FEE_recorded_by_user_id__e50e2c50_fk_OFFICER_U` (`recorded_by_user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `membership_fee` */

insert  into `membership_fee`(`fee_id_PK`,`amount`,`payment_date`,`payment_status`,`receipt_number`,`deposit_reference`,`member_id_FK`,`recorded_by_user_id_FK`,`payment_method`) values 
(1,100.00,'2026-08-31','Full Payment','REG-20260807080546-21-232323',NULL,1,48,'OTC Cash'),
(2,100.00,'2026-08-07','Full Payment','REG-20260807080552-bart',NULL,2,48,'Bank Transfer'),
(3,100.00,'2026-08-07','Full Payment','REG-20260807080539-142joe',NULL,3,48,'GCash');

/*Table structure for table `minutes` */

DROP TABLE IF EXISTS `minutes`;

CREATE TABLE `minutes` (
  `minutes_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `meeting_title` varchar(255) NOT NULL,
  `meeting_date` date NOT NULL,
  `venue` varchar(255) NOT NULL,
  `attendees` longtext NOT NULL,
  `agenda` longtext NOT NULL,
  `minutes_content` longtext NOT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `prepared_by_user_id_FK` int(11) DEFAULT NULL,
  `event_id_FK` int(11) DEFAULT NULL,
  `document_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`minutes_id_PK`),
  KEY `MINUTES_prepared_by_user_id__f10e2bf9_fk_OFFICER_U` (`prepared_by_user_id_FK`),
  KEY `MINUTES_event_id_FK_352800da_fk_EVENT_event_id_PK` (`event_id_FK`),
  KEY `MINUTES_document_id_FK_3dab1eff_fk_DOCUMENT_document_id_PK` (`document_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `minutes` */

/*Table structure for table `monthly_dues` */

DROP TABLE IF EXISTS `monthly_dues`;

CREATE TABLE `monthly_dues` (
  `dues_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `month_covered` varchar(50) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `payment_method` varchar(50) NOT NULL,
  `payment_status` varchar(50) NOT NULL,
  `receipt_number` varchar(100) DEFAULT NULL,
  `deduction_batch_reference` varchar(100) DEFAULT NULL,
  `remittance_reference` varchar(100) DEFAULT NULL,
  `member_id_FK` int(11) NOT NULL,
  `recorded_by_user_id_FK` int(11) NOT NULL,
  `payment_date` date DEFAULT NULL,
  `treasurer_status` varchar(50) NOT NULL,
  `treasurer_id_FK` int(11) DEFAULT NULL,
  `treasurer_remarks` longtext DEFAULT NULL,
  `treasurer_approved_at` datetime(6) DEFAULT NULL,
  `auditor_status` varchar(50) NOT NULL,
  `auditor_id_FK` int(11) DEFAULT NULL,
  `auditor_remarks` longtext DEFAULT NULL,
  `auditor_approved_at` datetime(6) DEFAULT NULL,
  `president_status` varchar(50) NOT NULL,
  `president_id_FK` int(11) DEFAULT NULL,
  `president_remarks` longtext DEFAULT NULL,
  `president_approved_at` datetime(6) DEFAULT NULL,
  `is_advance` tinyint(1) NOT NULL,
  PRIMARY KEY (`dues_id_PK`),
  KEY `MONTHLY_DUES_member_id_FK_70adcf99_fk_MEMBER_member_id_PK` (`member_id_FK`),
  KEY `MONTHLY_DUES_recorded_by_user_id__a84ebfb3_fk_OFFICER_U` (`recorded_by_user_id_FK`),
  KEY `MONTHLY_DUES_treasurer_id_FK_2ce5f468_fk_OFFICER_USER_user_id_PK` (`treasurer_id_FK`),
  KEY `MONTHLY_DUES_auditor_id_FK_fd49c27d_fk_OFFICER_USER_user_id_PK` (`auditor_id_FK`),
  KEY `MONTHLY_DUES_president_id_FK_08476f2c_fk_OFFICER_USER_user_id_PK` (`president_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `monthly_dues` */

insert  into `monthly_dues`(`dues_id_PK`,`month_covered`,`amount`,`payment_method`,`payment_status`,`receipt_number`,`deduction_batch_reference`,`remittance_reference`,`member_id_FK`,`recorded_by_user_id_FK`,`payment_date`,`treasurer_status`,`treasurer_id_FK`,`treasurer_remarks`,`treasurer_approved_at`,`auditor_status`,`auditor_id_FK`,`auditor_remarks`,`auditor_approved_at`,`president_status`,`president_id_FK`,`president_remarks`,`president_approved_at`,`is_advance`) values 
(1,'2026-09',50.00,'GCash','Full Payment','264839922',NULL,NULL,1,94,'2026-08-07','Treasurer Verified',49,'','2026-08-07 08:21:07.167053','Pending Auditor Review',NULL,NULL,NULL,'President Approved',48,NULL,'2026-08-07 08:26:29.686475',1),
(2,'2026-10',50.00,'GCash','Full Payment','264839922',NULL,NULL,1,94,'2026-08-07','Treasurer Verified',49,'','2026-08-07 08:20:58.215858','Pending Auditor Review',NULL,NULL,NULL,'President Approved',48,NULL,'2026-08-07 08:26:13.503783',1),
(3,'2026-11',50.00,'Salary Deduction','Full Payment',NULL,'For November','ISU-CAUFA-26-1',1,49,'2026-11-01','Treasurer Verified',NULL,NULL,NULL,'Pending Auditor Review',NULL,NULL,NULL,'President Approved',48,NULL,'2026-08-07 08:33:57.150569',0),
(4,'2026-11',50.00,'Salary Deduction','Full Payment',NULL,'For November','ISU-CAUFA-26-1',2,49,'2026-11-01','Treasurer Verified',NULL,NULL,NULL,'Pending Auditor Review',NULL,NULL,NULL,'President Approved',48,NULL,'2026-08-07 08:34:10.300239',0),
(5,'2026-11',50.00,'Salary Deduction','Full Payment',NULL,'For November','ISU-CAUFA-26-1',3,49,'2026-11-01','Treasurer Verified',NULL,NULL,NULL,'Pending Auditor Review',NULL,NULL,NULL,'President Approved',48,NULL,'2026-08-07 08:34:16.292583',0),
(6,'2026-12',50.00,'Cash OTC','Full Payment','OR-OTC-69911',NULL,NULL,3,49,'2026-08-07','Treasurer Approved',49,NULL,'2026-08-07 08:37:35.980185','Pending Auditor Review',NULL,NULL,NULL,'President Approved',48,NULL,'2026-08-07 08:38:21.020131',1);

/*Table structure for table `news_article` */

DROP TABLE IF EXISTS `news_article`;

CREATE TABLE `news_article` (
  `news_id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `slug` varchar(255) NOT NULL,
  `summary` longtext NOT NULL,
  `content` longtext NOT NULL,
  `featured_image` varchar(100) DEFAULT NULL,
  `event_date` date DEFAULT NULL,
  `event_time` time(6) DEFAULT NULL,
  `venue` varchar(255) NOT NULL,
  `video_url` varchar(200) NOT NULL,
  `video_thumbnail` varchar(100) DEFAULT NULL,
  `is_featured` tinyint(1) NOT NULL,
  `is_published` tinyint(1) NOT NULL,
  `published_at` datetime(6) DEFAULT NULL,
  `view_count` int(11) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `author_id` int(11) DEFAULT NULL,
  `category_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`news_id`),
  UNIQUE KEY `slug` (`slug`),
  KEY `NEWS_ARTICLE_author_id_04dc2507_fk_OFFICER_USER_user_id_PK` (`author_id`),
  KEY `NEWS_ARTICLE_category_id_630b7031_fk_NEWS_CATEGORY_category_id` (`category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `news_article` */

/*Table structure for table `news_category` */

DROP TABLE IF EXISTS `news_category`;

CREATE TABLE `news_category` (
  `category_id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `slug` varchar(100) NOT NULL,
  `description` longtext NOT NULL,
  `icon` varchar(50) NOT NULL,
  `order` int(11) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`category_id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `news_category` */

/*Table structure for table `news_gallery` */

DROP TABLE IF EXISTS `news_gallery`;

CREATE TABLE `news_gallery` (
  `gallery_id` int(11) NOT NULL AUTO_INCREMENT,
  `caption` varchar(255) NOT NULL,
  `image` varchar(100) NOT NULL,
  `is_featured` tinyint(1) NOT NULL,
  `order` int(11) NOT NULL,
  `uploaded_at` datetime(6) NOT NULL,
  `article_id` int(11) NOT NULL,
  PRIMARY KEY (`gallery_id`),
  KEY `NEWS_GALLERY_article_id_3ad83410_fk_NEWS_ARTICLE_news_id` (`article_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `news_gallery` */

/*Table structure for table `notification` */

DROP TABLE IF EXISTS `notification`;

CREATE TABLE `notification` (
  `notification_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `recipient_type` varchar(50) NOT NULL,
  `recipient_id` int(11) NOT NULL,
  `recipient_name` varchar(255) NOT NULL,
  `recipient_contact` varchar(255) DEFAULT NULL,
  `notification_type` varchar(50) NOT NULL,
  `message` longtext NOT NULL,
  `delivery_status` varchar(50) NOT NULL,
  `sent_at` datetime(6) NOT NULL,
  `category` varchar(20) DEFAULT NULL,
  `channel` varchar(20) DEFAULT NULL,
  `error_message` longtext DEFAULT NULL,
  `overdue_bucket` varchar(10) DEFAULT NULL,
  `related_post_id_FK` int(11) DEFAULT NULL,
  `scheduled_date` datetime(6) DEFAULT NULL,
  `is_read` tinyint(1) NOT NULL,
  PRIMARY KEY (`notification_id_PK`),
  KEY `NOTIFICATION_related_post_id_FK_e61541a2_fk_AID_TRACK` (`related_post_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `notification` */

insert  into `notification`(`notification_id_PK`,`recipient_type`,`recipient_id`,`recipient_name`,`recipient_contact`,`notification_type`,`message`,`delivery_status`,`sent_at`,`category`,`channel`,`error_message`,`overdue_bucket`,`related_post_id_FK`,`scheduled_date`,`is_read`) values 
(1,'member',1,'Jayjay D Mariano','jasminerotugal@gmail.com','membership_approved','Your ISU CAUFA membership registration has been approved. Welcome aboard, Jayjay D Mariano!','sent','2026-08-07 08:07:25.941268','general',NULL,NULL,NULL,NULL,NULL,1),
(2,'member',2,'Bartholomew Q Badongkadonks','yegan.kiru@gmail.com','membership_approved','Your ISU CAUFA membership registration has been approved. Welcome aboard, Bartholomew Q Badongkadonks!','sent','2026-08-07 08:07:30.475040','general',NULL,NULL,NULL,NULL,NULL,0),
(3,'member',3,'JUSTIN VON T VERGARA','justinvon.vergara_cyn@isu.edu.ph','membership_approved','Your ISU CAUFA membership registration has been approved. Welcome aboard, JUSTIN VON T VERGARA!','sent','2026-08-07 08:07:36.693753','general',NULL,NULL,NULL,NULL,NULL,0),
(4,'member',1,'Jayjay D Mariano','jasminerotugal@gmail.com','Payment Approved','Your monthly dues payment for 2026-10 (₱50.00) has been approved. Thank you for your contribution.','sent','2026-08-07 08:26:13.604634','payment',NULL,NULL,NULL,NULL,NULL,1),
(5,'member',1,'Jayjay D Mariano','jasminerotugal@gmail.com','Payment Approved','Your monthly dues payment for 2026-09 (₱50.00) has been approved. Thank you for your contribution.','sent','2026-08-07 08:26:29.700575','payment',NULL,NULL,NULL,NULL,NULL,1),
(6,'member',1,'Jayjay D Mariano','jasminerotugal@gmail.com','Payment Approved','Your monthly dues payment for 2026-11 (₱50.00) has been approved. Thank you for your contribution.','sent','2026-08-07 08:33:57.176549','payment',NULL,NULL,NULL,NULL,NULL,0),
(7,'member',2,'Bartholomew Q Badongkadonks','yegan.kiru@gmail.com','Payment Approved','Your monthly dues payment for 2026-11 (₱50.00) has been approved. Thank you for your contribution.','sent','2026-08-07 08:34:10.323872','payment',NULL,NULL,NULL,NULL,NULL,0),
(8,'member',3,'JUSTIN VON T VERGARA','justinvon.vergara_cyn@isu.edu.ph','Payment Approved','Your monthly dues payment for 2026-11 (₱50.00) has been approved. Thank you for your contribution.','sent','2026-08-07 08:34:16.309691','payment',NULL,NULL,NULL,NULL,NULL,0),
(9,'member',3,'JUSTIN VON T VERGARA','justinvon.vergara_cyn@isu.edu.ph','Payment Approved','Your monthly dues payment for 2026-12 (₱50.00) has been approved. Thank you for your contribution.','sent','2026-08-07 08:38:21.039230','payment',NULL,NULL,NULL,NULL,NULL,0),
(10,'member',1,'Jayjay D Mariano',NULL,'Claim Update','Your Medical Aid claim has been approved by the Treasurer and forwarded to the Auditor.','Sent','2026-08-07 08:40:54.750948',NULL,'in_app',NULL,NULL,NULL,NULL,0),
(11,'member',2,'Bartholomew Q Badongkadonks','yegan.kiru@gmail.com','Aid Contribution Required','A Medical Aid request by Jayjay D Mariano has been approved. Your contribution of ₱10,000.00 is requested.','sent','2026-08-07 08:54:18.623269','contribution',NULL,NULL,NULL,NULL,NULL,0),
(12,'member',3,'JUSTIN VON T VERGARA','justinvon.vergara_cyn@isu.edu.ph','Aid Contribution Required','A Medical Aid request by Jayjay D Mariano has been approved. Your contribution of ₱10,000.00 is requested.','sent','2026-08-07 08:54:18.631108','contribution',NULL,NULL,NULL,NULL,NULL,0);

/*Table structure for table `officer_profile` */

DROP TABLE IF EXISTS `officer_profile`;

CREATE TABLE `officer_profile` (
  `officer_profile_id` int(11) NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `position` varchar(100) NOT NULL,
  `category` varchar(50) NOT NULL,
  `department` varchar(255) DEFAULT NULL,
  `school_year` varchar(50) DEFAULT NULL,
  `term_start` date DEFAULT NULL,
  `term_end` date DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `facebook` varchar(200) DEFAULT NULL,
  `biography` longtext DEFAULT NULL,
  `photo` varchar(100) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `created_by_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`officer_profile_id`),
  KEY `OFFICER_PROFILE_created_by_id_d435d405_fk_OFFICER_U` (`created_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `officer_profile` */

/*Table structure for table `officer_user` */

DROP TABLE IF EXISTS `officer_user`;

CREATE TABLE `officer_user` (
  `user_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `username` varchar(150) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` varchar(50) NOT NULL,
  `account_status` varchar(50) NOT NULL,
  `term_start` date DEFAULT NULL,
  `term_end` date DEFAULT NULL,
  `mfa_secret` varchar(255) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `mfa_enabled` tinyint(1) NOT NULL,
  `last_mfa_email_sent_at` datetime(6) DEFAULT NULL,
  `department_id_FK` int(11) DEFAULT NULL,
  `email` varchar(255) DEFAULT NULL,
  `must_change_password` tinyint(1) NOT NULL,
  PRIMARY KEY (`user_id_PK`),
  UNIQUE KEY `username` (`username`),
  KEY `OFFICER_USER_department_id_FK_cc12815d_fk_DEPARTMEN` (`department_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=97 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `officer_user` */

insert  into `officer_user`(`user_id_PK`,`full_name`,`username`,`password_hash`,`role`,`account_status`,`term_start`,`term_end`,`mfa_secret`,`created_at`,`updated_at`,`mfa_enabled`,`last_mfa_email_sent_at`,`department_id_FK`,`email`,`must_change_password`) values 
(39,'System Backfill','system_backfill','','System','Inactive',NULL,NULL,NULL,'2026-07-22 11:56:41.818208','2026-07-22 11:56:41.818208',0,NULL,NULL,NULL,0),
(40,'Superadmin Admin Von','adminvon','3b506d4da7b78c2d1504c0d487e6f1c6bec5ad0a6db040d51a7b5d2444121a0b','Superadmin','Active',NULL,NULL,NULL,'2026-07-22 12:07:09.665684','2026-07-22 12:07:09.665684',0,NULL,NULL,'adminvon@caufa.local',0),
(48,'President Account','president','f4751fdedd081c907d7e8fd7d5ee8660e18cead802a967d17188a034faaa7edb','President','Active',NULL,NULL,'599bf7c18b565961da4adabd34e99cfe','2026-08-04 11:28:24.008010','2026-08-04 11:30:06.563945',1,'2026-08-07 09:05:27.211643',NULL,'vdark699@gmail.com',0),
(49,'BEN HAMMAD GUDANI','treasurer','pbkdf2_sha256$260000$a288c7af9da857345161a4de0c150517$2f8d04f0965b5cf9597bd7e8ffbcc761cbe1f0dee957ff8e2da5201d203963b9','Treasurer','Active','2026-08-04','2026-12-05','4e0051ecde7392ece96ce90f6e2424bd','2026-08-04 12:53:31.644934','2026-08-07 01:14:06.532723',1,'2026-08-07 09:09:38.646878',NULL,'manchoco69@gmail.com',0),
(50,'JAYEM REOJANO','auditor','pbkdf2_sha256$260000$09fa369cf18937102f4c990cb12a6df3$4291a8b90ca2d3ca891942e6d90dbb8df7b8e21fa57c6aa79f2ebbb268c1bfb8','Auditor','Active','2026-08-04','2026-12-05','b6b63ff232fb8e3175898630643faae1','2026-08-04 12:53:54.280192','2026-08-07 01:13:54.504669',1,'2026-08-07 09:02:31.069205',NULL,'yegan.kiru@gmail.com',0),
(57,'ARISTEO UBANA','secretary','f4751fdedd081c907d7e8fd7d5ee8660e18cead802a967d17188a034faaa7edb','Secretary','Active','2026-08-04','2026-12-05',NULL,'2026-08-04 14:54:05.995866','2026-08-04 14:54:05.995866',0,NULL,3,'qwerty@gmail.com',0),
(58,'TOLITHS SAMBAL','pio','f4751fdedd081c907d7e8fd7d5ee8660e18cead802a967d17188a034faaa7edb','Public Information Officer','Active','2026-08-04','2026-12-05',NULL,'2026-08-04 14:54:33.246179','2026-08-04 14:54:33.246179',0,NULL,4,'lol123@gmail.com',0),
(94,'Jayjay D Mariano','21-232323','pbkdf2_sha256$260000$95376f310fb66198f27545ab259dbfff$350cb9103814028f80208acac6d590ea335a78989f4fde0eaddcb5cbc410f4bd','Member','Active',NULL,NULL,NULL,'2026-08-07 08:07:23.094117','2026-08-07 08:07:23.094117',0,NULL,NULL,'jasminerotugal@gmail.com',0),
(95,'Bartholomew Q Badongkadonks','bart','pbkdf2_sha256$260000$ef3c721f5a197491c4cd4efb8c7c82a4$5738c2e51a9d5fc24a022f589827f9ab3793f958e8a35c94396cba8b80b9634b','Member','Active',NULL,NULL,NULL,'2026-08-07 08:07:30.372503','2026-08-07 08:07:30.372503',0,NULL,NULL,'yegan.kiru@gmail.com',0),
(96,'JUSTIN VON T VERGARA','142joe','pbkdf2_sha256$260000$a25dcb5c6279dd6653bf054053c1e607$47a994209463cd7ca100af55baa2af650955c4a33c63a31c02f924e5833aee19','Member','Active',NULL,NULL,NULL,'2026-08-07 08:07:36.659620','2026-08-07 08:07:36.659620',0,NULL,NULL,'justinvon.vergara_cyn@isu.edu.ph',0);

/*Table structure for table `organization_fund_report` */

DROP TABLE IF EXISTS `organization_fund_report`;

CREATE TABLE `organization_fund_report` (
  `report_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `report_period` varchar(20) NOT NULL,
  `report_type` varchar(20) NOT NULL,
  `report_status` varchar(50) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `approved_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `approved_by_user_id_FK` int(11) DEFAULT NULL,
  `prepared_by_user_id_FK` int(11) NOT NULL,
  PRIMARY KEY (`report_id_PK`),
  KEY `ORGANIZATION_FUND_RE_approved_by_user_id__a8823df8_fk_OFFICER_U` (`approved_by_user_id_FK`),
  KEY `ORGANIZATION_FUND_RE_prepared_by_user_id__f419a1e5_fk_OFFICER_U` (`prepared_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `organization_fund_report` */

/*Table structure for table `outgoing_email` */

DROP TABLE IF EXISTS `outgoing_email`;

CREATE TABLE `outgoing_email` (
  `outgoing_email_id` int(11) NOT NULL AUTO_INCREMENT,
  `recipient_list` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`recipient_list`)),
  `subject` varchar(255) NOT NULL,
  `html_template` varchar(255) NOT NULL,
  `context` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`context`)),
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `sent_at` datetime(6) DEFAULT NULL,
  `error_message` longtext NOT NULL,
  `retry_count` int(11) NOT NULL,
  PRIMARY KEY (`outgoing_email_id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `outgoing_email` */

insert  into `outgoing_email`(`outgoing_email_id`,`recipient_list`,`subject`,`html_template`,`context`,`status`,`created_at`,`sent_at`,`error_message`,`retry_count`) values 
(1,'[\"manchoco69@gmail.com\"]','CAUFA MFA Verification Code','emails/mfa_challenge.html','{\"full_name\": \"BEN HAMMAD GUDANI\", \"otp_code\": \"705765\", \"expiry_minutes\": 5}','sent','2026-08-07 08:05:33.915574','2026-08-07 08:05:40.277658','',0),
(2,'[\"jasminerotugal@gmail.com\"]','Welcome to ISU CAUFA – Membership Approved!','emails/member_added.html','{\"full_name\": \"Jayjay D Mariano\", \"employee_id\": \"21-232323\", \"date_joined\": \"August 07, 2026\", \"department\": \"CCSICT\", \"monthly_dues_amount\": 50.0, \"membership_fee_amount\": 100.0, \"officer_contact\": \"\", \"generated_password\": \"[]I}14{gCTXD\"}','sent','2026-08-07 08:07:25.888694','2026-08-07 08:07:37.768385','',0),
(3,'[\"yegan.kiru@gmail.com\"]','Welcome to ISU CAUFA – Membership Approved!','emails/member_added.html','{\"full_name\": \"Bartholomew Q Badongkadonks\", \"employee_id\": \"bart\", \"date_joined\": \"August 07, 2026\", \"department\": \"CCSICT\", \"monthly_dues_amount\": 50.0, \"membership_fee_amount\": 100.0, \"officer_contact\": \"\", \"generated_password\": \"UY<7Wya=t_0a\"}','sent','2026-08-07 08:07:30.469113','2026-08-07 08:07:44.704131','',0),
(4,'[\"justinvon.vergara_cyn@isu.edu.ph\"]','Welcome to ISU CAUFA – Membership Approved!','emails/member_added.html','{\"full_name\": \"JUSTIN VON T VERGARA\", \"employee_id\": \"142joe\", \"date_joined\": \"August 07, 2026\", \"department\": \"CCSICT\", \"monthly_dues_amount\": 50.0, \"membership_fee_amount\": 100.0, \"officer_contact\": \"\", \"generated_password\": \"}fo:=H:c6KrA\"}','sent','2026-08-07 08:07:36.687987','2026-08-07 08:07:50.197894','',0),
(5,'[\"yegan.kiru@gmail.com\"]','CAUFA MFA Verification Code','emails/mfa_challenge.html','{\"full_name\": \"JAYEM REOJANO\", \"otp_code\": \"837953\", \"expiry_minutes\": 5}','sent','2026-08-07 08:31:37.249871','2026-08-07 08:31:44.293995','',0),
(6,'[\"vdark699@gmail.com\"]','CAUFA MFA Verification Code','emails/mfa_challenge.html','{\"full_name\": \"President Account\", \"otp_code\": \"041526\", \"expiry_minutes\": 5}','sent','2026-08-07 08:32:42.621011','2026-08-07 08:32:49.479688','',0),
(7,'[\"manchoco69@gmail.com\"]','CAUFA MFA Verification Code','emails/mfa_challenge.html','{\"full_name\": \"BEN HAMMAD GUDANI\", \"otp_code\": \"714000\", \"expiry_minutes\": 5}','sent','2026-08-07 08:36:58.332459','2026-08-07 08:37:05.448290','',0),
(8,'[\"yegan.kiru@gmail.com\"]','CAUFA MFA Verification Code','emails/mfa_challenge.html','{\"full_name\": \"JAYEM REOJANO\", \"otp_code\": \"931957\", \"expiry_minutes\": 5}','sent','2026-08-07 09:02:31.070207','2026-08-07 09:02:37.206309','',0),
(9,'[\"vdark699@gmail.com\"]','CAUFA MFA Verification Code','emails/mfa_challenge.html','{\"full_name\": \"President Account\", \"otp_code\": \"349083\", \"expiry_minutes\": 5}','sent','2026-08-07 09:05:27.211643','2026-08-07 09:05:33.656395','',0),
(10,'[\"manchoco69@gmail.com\"]','CAUFA MFA Verification Code','emails/mfa_challenge.html','{\"full_name\": \"BEN HAMMAD GUDANI\", \"otp_code\": \"153141\", \"expiry_minutes\": 5}','sent','2026-08-07 09:09:38.646878','2026-08-07 09:09:44.199243','',0);

/*Table structure for table `payroll_batch` */

DROP TABLE IF EXISTS `payroll_batch`;

CREATE TABLE `payroll_batch` (
  `batch_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `payroll_period` varchar(7) NOT NULL,
  `total_amount` decimal(12,2) NOT NULL,
  `member_count` int(11) NOT NULL,
  `notes` longtext NOT NULL,
  `hardcopy_reference` varchar(100) DEFAULT NULL,
  `status` varchar(50) NOT NULL,
  `auditor_verified_at` datetime(6) DEFAULT NULL,
  `auditor_remarks` longtext DEFAULT NULL,
  `returned_reason` longtext DEFAULT NULL,
  `president_approved_at` datetime(6) DEFAULT NULL,
  `president_remarks` longtext DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `archive_id_FK` int(11) DEFAULT NULL,
  `auditor_verified_by_user_id_FK` int(11) DEFAULT NULL,
  `president_approved_by_user_id_FK` int(11) DEFAULT NULL,
  `recorded_by_user_id_FK` int(11) NOT NULL,
  `returned_by_user_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`batch_id_PK`),
  KEY `PAYROLL_BATCH_archive_id_FK_c8cd48a0_fk_transacti` (`archive_id_FK`),
  KEY `PAYROLL_BATCH_auditor_verified_by__1214d668_fk_OFFICER_U` (`auditor_verified_by_user_id_FK`),
  KEY `PAYROLL_BATCH_president_approved_b_d7cb885f_fk_OFFICER_U` (`president_approved_by_user_id_FK`),
  KEY `PAYROLL_BATCH_recorded_by_user_id__f63b35cb_fk_OFFICER_U` (`recorded_by_user_id_FK`),
  KEY `PAYROLL_BATCH_returned_by_user_id__25fe28ed_fk_OFFICER_U` (`returned_by_user_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `payroll_batch` */

/*Table structure for table `payroll_deduction` */

DROP TABLE IF EXISTS `payroll_deduction`;

CREATE TABLE `payroll_deduction` (
  `deduction_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `amount` decimal(10,2) NOT NULL,
  `category` varchar(50) NOT NULL,
  `fund_impact` varchar(10) NOT NULL,
  `month_covered` varchar(7) DEFAULT NULL,
  `notes` longtext NOT NULL,
  `aid_tracking_post_id_FK` int(11) DEFAULT NULL,
  `batch_id_FK` int(11) NOT NULL,
  `member_id_FK` int(11) NOT NULL,
  PRIMARY KEY (`deduction_id_PK`),
  KEY `PAYROLL_DEDUCTION_aid_tracking_post_id_14171c63_fk_AID_TRACK` (`aid_tracking_post_id_FK`),
  KEY `PAYROLL_DED_batch_i_0b9b21_idx` (`batch_id_FK`,`category`),
  KEY `PAYROLL_DED_member__4008e1_idx` (`member_id_FK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `payroll_deduction` */

/*Table structure for table `photo` */

DROP TABLE IF EXISTS `photo`;

CREATE TABLE `photo` (
  `photo_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `image` varchar(100) NOT NULL,
  `caption` varchar(255) NOT NULL,
  `is_featured` tinyint(1) NOT NULL,
  `uploaded_at` datetime(6) NOT NULL,
  `album_id` int(11) NOT NULL,
  `uploaded_by_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`photo_id_PK`),
  KEY `PHOTO_album_id_ad2092d5_fk_ALBUM_album_id_PK` (`album_id`),
  KEY `PHOTO_uploaded_by_id_ba7c3a3a_fk_OFFICER_USER_user_id_PK` (`uploaded_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `photo` */

/*Table structure for table `push_subscription` */

DROP TABLE IF EXISTS `push_subscription`;

CREATE TABLE `push_subscription` (
  `subscription_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `officer_id_FK` int(11) NOT NULL,
  `endpoint` varchar(500) NOT NULL,
  `p256dh_key` varchar(256) NOT NULL,
  `auth_key` varchar(128) NOT NULL,
  `user_agent` varchar(500) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`subscription_id_PK`),
  UNIQUE KEY `PUSH_SUBSCRIPTION_officer_id_FK_endpoint_d8da377b_uniq` (`officer_id_FK`,`endpoint`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `push_subscription` */

/*Table structure for table `revision_log` */

DROP TABLE IF EXISTS `revision_log`;

CREATE TABLE `revision_log` (
  `log_id` int(11) NOT NULL AUTO_INCREMENT,
  `object_id` int(10) unsigned NOT NULL CHECK (`object_id` >= 0),
  `rejection_reason` longtext NOT NULL,
  `snapshot_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`snapshot_data`)),
  `created_at` datetime(6) NOT NULL,
  `auditor_id_FK` int(11) DEFAULT NULL,
  `content_type_id` int(11) NOT NULL,
  PRIMARY KEY (`log_id`),
  KEY `revision_log_auditor_id_FK_86a7849b_fk_OFFICER_USER_user_id_PK` (`auditor_id_FK`),
  KEY `revision_lo_content_6da5e6_idx` (`content_type_id`,`object_id`),
  KEY `revision_lo_created_91651d_idx` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `revision_log` */

/*Table structure for table `salary_deduction_exemption` */

DROP TABLE IF EXISTS `salary_deduction_exemption`;

CREATE TABLE `salary_deduction_exemption` (
  `exemption_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `month_covered` varchar(50) NOT NULL,
  `reason` longtext DEFAULT NULL,
  `status` varchar(50) NOT NULL,
  `requested_at` datetime(6) NOT NULL,
  `requested_by_member` tinyint(1) NOT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `review_remarks` longtext DEFAULT NULL,
  `member_id_FK` int(11) NOT NULL,
  `reviewed_by_user_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`exemption_id_PK`),
  UNIQUE KEY `salary_deduction_exempti_member_id_FK_month_cover_uniq` (`member_id_FK`,`month_covered`),
  KEY `salary_deduction_exe_reviewed_by_fk_officer` (`reviewed_by_user_id_FK`),
  CONSTRAINT `salary_deduction_exe_member_id_FK_fk_member` FOREIGN KEY (`member_id_FK`) REFERENCES `member` (`member_id_PK`),
  CONSTRAINT `salary_deduction_exe_reviewed_by_fk_officer` FOREIGN KEY (`reviewed_by_user_id_FK`) REFERENCES `officer_user` (`user_id_PK`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `salary_deduction_exemption` */

/*Table structure for table `sensitive_read_log` */

DROP TABLE IF EXISTS `sensitive_read_log`;

CREATE TABLE `sensitive_read_log` (
  `read_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `module` varchar(100) NOT NULL,
  `record_id` int(11) NOT NULL,
  `purpose` varchar(255) NOT NULL,
  `timestamp` datetime(6) NOT NULL,
  `user_id_FK` int(11) NOT NULL,
  `device_info` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`read_id_PK`),
  KEY `SENSITIVE_READ_LOG_user_id_FK_f41bb5ec_fk_OFFICER_U` (`user_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=58 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `sensitive_read_log` */

insert  into `sensitive_read_log`(`read_id_PK`,`module`,`record_id`,`purpose`,`timestamp`,`user_id_FK`,`device_info`) values 
(1,'medical_aid',1,'Treasurer','2026-08-07 08:20:26.672184',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(2,'medical_aid',1,'Auditor','2026-08-07 08:21:14.581711',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(3,'medical_aid',1,'Treasurer','2026-08-07 08:22:01.929900',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(4,'medical_aid',1,'Auditor','2026-08-07 08:22:02.108391',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(5,'medical_aid',1,'Auditor','2026-08-07 08:22:02.415010',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(6,'medical_aid',1,'Auditor','2026-08-07 08:22:02.798079',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(7,'medical_aid',1,'Auditor','2026-08-07 08:22:03.757042',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(8,'medical_aid',1,'Auditor','2026-08-07 08:22:04.066559',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(9,'medical_aid',1,'Auditor','2026-08-07 08:26:21.478736',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(10,'medical_aid',1,'Auditor','2026-08-07 08:26:21.708982',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(11,'medical_aid',1,'Auditor','2026-08-07 08:26:21.983096',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(12,'medical_aid',1,'Auditor','2026-08-07 08:26:36.885951',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(13,'medical_aid',1,'Auditor','2026-08-07 08:26:37.533835',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(14,'medical_aid',1,'Auditor','2026-08-07 08:26:37.892765',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(15,'medical_aid',1,'Treasurer','2026-08-07 08:26:51.896148',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(16,'medical_aid',1,'Auditor','2026-08-07 08:27:04.642357',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(17,'medical_aid',1,'Auditor','2026-08-07 08:32:04.741493',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(18,'medical_aid',1,'Treasurer','2026-08-07 08:32:13.855688',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(19,'medical_aid',1,'Auditor','2026-08-07 08:32:13.943873',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(20,'medical_aid',1,'Auditor','2026-08-07 08:32:14.230708',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(21,'medical_aid',1,'Auditor','2026-08-07 08:32:14.647994',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(22,'medical_aid',1,'Auditor','2026-08-07 08:32:15.016158',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(23,'medical_aid',1,'Auditor','2026-08-07 08:32:15.471042',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(24,'medical_aid',1,'Auditor','2026-08-07 08:34:04.291662',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(25,'medical_aid',1,'Auditor','2026-08-07 08:34:04.543574',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(26,'medical_aid',1,'Auditor','2026-08-07 08:34:04.938451',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(27,'medical_aid',1,'Auditor','2026-08-07 08:34:22.919837',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(28,'medical_aid',1,'Auditor','2026-08-07 08:34:23.427805',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(29,'medical_aid',1,'Auditor','2026-08-07 08:34:23.874034',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(30,'medical_aid',1,'Treasurer','2026-08-07 08:34:32.227774',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(31,'medical_aid',1,'Treasurer','2026-08-07 08:37:27.782853',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(32,'medical_aid',1,'Auditor','2026-08-07 08:37:42.378917',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(33,'medical_aid',1,'Treasurer','2026-08-07 08:37:48.759586',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(34,'medical_aid',1,'Auditor','2026-08-07 08:37:48.888212',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(35,'medical_aid',1,'Auditor','2026-08-07 08:37:49.176031',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(36,'medical_aid',1,'Auditor','2026-08-07 08:37:49.593649',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(37,'medical_aid',1,'Auditor','2026-08-07 08:37:49.942674',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(38,'medical_aid',1,'Auditor','2026-08-07 08:37:50.302927',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(39,'medical_aid',1,'Auditor','2026-08-07 08:38:27.897973',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(40,'medical_aid',1,'Auditor','2026-08-07 08:38:28.230709',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(41,'medical_aid',1,'Auditor','2026-08-07 08:38:28.620405',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(42,'medical_aid',1,'Treasurer','2026-08-07 08:38:34.845360',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(43,'medical_aid',1,'Auditor','2026-08-07 08:41:04.671937',50,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(44,'medical_aid',1,'Treasurer','2026-08-07 08:41:17.679907',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(45,'medical_aid',1,'President','2026-08-07 08:41:28.616973',48,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'),
(46,'medical_aid',1,'President','2026-08-07 08:41:28.635998',48,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'),
(47,'medical_aid',1,'President','2026-08-07 08:45:01.566008',48,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'),
(48,'medical_aid',1,'President','2026-08-07 08:45:01.593389',48,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'),
(49,'medical_aid',1,'Treasurer','2026-08-07 08:45:04.454954',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(50,'medical_aid',1,'President','2026-08-07 08:50:55.869448',48,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'),
(51,'medical_aid',1,'President','2026-08-07 08:50:56.338158',48,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'),
(52,'medical_aid',1,'Treasurer','2026-08-07 08:55:29.820024',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(53,'medical_aid',1,'Treasurer','2026-08-07 09:02:01.382580',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(54,'medical_aid',1,'Treasurer','2026-08-07 09:10:02.885392',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(55,'medical_aid',1,'Treasurer','2026-08-07 09:12:14.627924',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(56,'medical_aid',1,'Treasurer','2026-08-07 09:15:45.189765',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0'),
(57,'medical_aid',1,'Treasurer','2026-08-07 09:16:21.800054',49,'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0');

/*Table structure for table `supporting_proof` */

DROP TABLE IF EXISTS `supporting_proof`;

CREATE TABLE `supporting_proof` (
  `proof_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `object_id` int(10) unsigned NOT NULL CHECK (`object_id` >= 0),
  `file_path` varchar(500) NOT NULL,
  `file_name` varchar(255) NOT NULL,
  `file_type` varchar(100) NOT NULL,
  `file_sha256` varchar(64) NOT NULL,
  `row_signature` varchar(64) NOT NULL,
  `uploaded_at` datetime(6) NOT NULL,
  `content_type_id` int(11) NOT NULL,
  `uploaded_by_user_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`proof_id_PK`),
  KEY `SUPPORTING_PROOF_uploaded_by_user_id__a400d09d_fk_OFFICER_U` (`uploaded_by_user_id_FK`),
  KEY `SUPPORTING__content_09c351_idx` (`content_type_id`,`object_id`),
  KEY `SUPPORTING__uploade_b01f8c_idx` (`uploaded_at`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `supporting_proof` */

insert  into `supporting_proof`(`proof_id_PK`,`object_id`,`file_path`,`file_name`,`file_type`,`file_sha256`,`row_signature`,`uploaded_at`,`content_type_id`,`uploaded_by_user_id_FK`) values 
(1,1,'supporting_proofs/2026/08/07/FB_IMG_1786071674299.jpg','FB_IMG_1786071674299.jpg','image/jpeg','bbe1e715f57d1a4c71e9e24f584ca2f1bd0733659db75b20bb90b1c81a0226d4','4a786c0a50a70152cb4ca975ec1c0cc458692a451b5b68efa0618612b7c849cd','2026-08-07 08:05:39.719107',1,NULL),
(2,2,'supporting_proofs/2026/08/07/inbound4660217117719719513.jpg','inbound4660217117719719513.jpg','image/jpeg','ea0e3057d2fa71f1af4fc1aa4e7a55049d60d81f536e86dff8d5d123169a8f9b','e254591f206dc9285f4113d1c7a95a1093be50c0ce11d0de4ff7995bea13308d','2026-08-07 08:05:46.488987',1,NULL),
(3,3,'supporting_proofs/2026/08/07/Screenshot_20260807_120206_com.BlackFoxEntertainment.DriftLegends2.jpg','Screenshot_20260807_120206_com.BlackFoxEntertainment.DriftLegends2.jpg','image/jpeg','5ee0178af17e14dd6ef0f8702781ced9ce1d42d2d52d4f5ce9e4313582036041','c142424166536269638c7afd75e7f3a5650b39ab497dea253c3d831d529c6438','2026-08-07 08:05:52.496809',1,NULL),
(4,1,'supporting_proofs/2026/08/07/inbound4660217117719719513.jpg','inbound4660217117719719513.jpg','image/jpeg','ea0e3057d2fa71f1af4fc1aa4e7a55049d60d81f536e86dff8d5d123169a8f9b','ea2706a53827b45a0582a253efdd3e0041970e4dad4315e3366de606a5dffb4e','2026-08-07 08:07:25.870203',2,48),
(5,2,'supporting_proofs/2026/08/07/Screenshot_20260807_120206_com.BlackFoxEntertainment.DriftLegends2.jpg','Screenshot_20260807_120206_com.BlackFoxEntertainment.DriftLegends2.jpg','image/jpeg','5ee0178af17e14dd6ef0f8702781ced9ce1d42d2d52d4f5ce9e4313582036041','b4be2c8a097b5862be3068886a055dbc6d11b32420d3eecb64ee690233cc54d3','2026-08-07 08:07:30.429162',2,48),
(6,3,'supporting_proofs/2026/08/07/FB_IMG_1786071674299.jpg','FB_IMG_1786071674299.jpg','image/jpeg','bbe1e715f57d1a4c71e9e24f584ca2f1bd0733659db75b20bb90b1c81a0226d4','1a03873edce8fac9443a9af10c64455242304deb5eed2744957883d79ab9aed5','2026-08-07 08:07:36.675224',2,48),
(7,1,'supporting_proofs/2026/08/07/inbound5980568772362936919.jpg','inbound5980568772362936919.jpg','image/jpeg','ea0e3057d2fa71f1af4fc1aa4e7a55049d60d81f536e86dff8d5d123169a8f9b','ea2706a53827b45a0582a253efdd3e0041970e4dad4315e3366de606a5dffb4e','2026-08-07 08:11:32.401764',5,94),
(8,1,'supporting_proofs/2026/08/07/inbound6514084795037994854.jpg','inbound6514084795037994854.jpg','image/jpeg','ea0e3057d2fa71f1af4fc1aa4e7a55049d60d81f536e86dff8d5d123169a8f9b','ea2706a53827b45a0582a253efdd3e0041970e4dad4315e3366de606a5dffb4e','2026-08-07 08:12:08.653369',2,94);

/*Table structure for table `system_setting` */

DROP TABLE IF EXISTS `system_setting`;

CREATE TABLE `system_setting` (
  `setting_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(100) NOT NULL,
  `setting_value` longtext NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `updated_by_id_FK` int(11) DEFAULT NULL,
  PRIMARY KEY (`setting_id_PK`),
  UNIQUE KEY `setting_key` (`setting_key`),
  KEY `SYSTEM_SETTING_updated_by_id_FK_d79d01db_fk_OFFICER_U` (`updated_by_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `system_setting` */

insert  into `system_setting`(`setting_id_PK`,`setting_key`,`setting_value`,`updated_at`,`updated_by_id_FK`) values 
(1,'safety_threshold','20000','2026-08-07 08:06:08.954542',NULL);

/*Table structure for table `transaction_archive` */

DROP TABLE IF EXISTS `transaction_archive`;

CREATE TABLE `transaction_archive` (
  `archive_id_PK` int(11) NOT NULL AUTO_INCREMENT,
  `transaction_type` varchar(50) NOT NULL,
  `record_id` int(11) NOT NULL,
  `member_name` varchar(255) NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `validated_amount` decimal(10,2) DEFAULT NULL,
  `status` varchar(50) NOT NULL,
  `payment_method` varchar(50) DEFAULT NULL,
  `release_reference` varchar(100) DEFAULT NULL,
  `verified_at` datetime(6) DEFAULT NULL,
  `archived_at` datetime(6) NOT NULL,
  `archived_by_user_id_FK` int(11) DEFAULT NULL,
  `member_id_FK` int(11) DEFAULT NULL,
  `released_by_user_id_FK` int(11) DEFAULT NULL,
  `fiscal_term` varchar(50) DEFAULT NULL,
  PRIMARY KEY (`archive_id_PK`),
  KEY `transaction_archive_archived_by_user_id__95d87e41_fk_OFFICER_U` (`archived_by_user_id_FK`),
  KEY `transaction_archive_member_id_FK_166fdd68_fk_MEMBER_member_id_PK` (`member_id_FK`),
  KEY `transaction_archive_released_by_user_id__7db2dcd2_fk_OFFICER_U` (`released_by_user_id_FK`),
  KEY `transaction_transac_4a6ac9_idx` (`transaction_type`,`record_id`),
  KEY `transaction_status_abeab9_idx` (`status`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `transaction_archive` */

insert  into `transaction_archive`(`archive_id_PK`,`transaction_type`,`record_id`,`member_name`,`amount`,`validated_amount`,`status`,`payment_method`,`release_reference`,`verified_at`,`archived_at`,`archived_by_user_id_FK`,`member_id_FK`,`released_by_user_id_FK`,`fiscal_term`) values 
(1,'monthly_dues',2,'Jayjay D Mariano',50.00,NULL,'Auditor Verified','GCash',NULL,'2026-08-06 16:00:00.000000','2026-08-07 08:26:13.489419',48,1,NULL,NULL),
(2,'monthly_dues',1,'Jayjay D Mariano',50.00,NULL,'Auditor Verified','GCash',NULL,'2026-08-06 16:00:00.000000','2026-08-07 08:26:29.668031',48,1,NULL,NULL),
(3,'monthly_dues',3,'Jayjay D Mariano',50.00,NULL,'Auditor Verified','Salary Deduction',NULL,'2026-10-31 16:00:00.000000','2026-08-07 08:33:57.127132',48,1,NULL,NULL),
(4,'monthly_dues',4,'Bartholomew Q Badongkadonks',50.00,NULL,'Auditor Verified','Salary Deduction',NULL,'2026-10-31 16:00:00.000000','2026-08-07 08:34:10.289830',48,2,NULL,NULL),
(5,'monthly_dues',5,'JUSTIN VON T VERGARA',50.00,NULL,'Auditor Verified','Salary Deduction',NULL,'2026-10-31 16:00:00.000000','2026-08-07 08:34:16.284331',48,3,NULL,NULL),
(6,'monthly_dues',6,'JUSTIN VON T VERGARA',50.00,NULL,'Auditor Verified','Cash OTC',NULL,'2026-08-06 16:00:00.000000','2026-08-07 08:38:21.000610',48,3,NULL,NULL),
(7,'medical_aid',1,'Jayjay D Mariano',20000.00,20000.00,'Approved',NULL,NULL,'2026-08-06 16:00:00.000000','2026-08-07 08:54:05.088506',48,1,NULL,NULL);

/*Table structure for table `transaction_verification` */

DROP TABLE IF EXISTS `transaction_verification`;

CREATE TABLE `transaction_verification` (
  `verification_id` int(11) NOT NULL AUTO_INCREMENT,
  `table_name` varchar(50) NOT NULL,
  `record_id` int(11) NOT NULL,
  `verification_status` varchar(50) NOT NULL,
  `verified_at` datetime(6) DEFAULT NULL,
  `approved_at` datetime(6) DEFAULT NULL,
  `auditor_id_FK` int(11) DEFAULT NULL,
  `president_id_FK` int(11) DEFAULT NULL,
  `auditor_remarks` longtext DEFAULT NULL,
  `evidence_file_hash` varchar(255) DEFAULT NULL,
  `evidence_file_path` varchar(500) DEFAULT NULL,
  `return_count` int(11) NOT NULL,
  `returned_by_auditor_id_FK` int(11) DEFAULT NULL,
  `returned_reason` longtext DEFAULT NULL,
  `target_category` varchar(50) DEFAULT NULL,
  `deposit_slip_reference` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`verification_id`),
  KEY `transaction_verifica_auditor_id_FK_36530d09_fk_OFFICER_U` (`auditor_id_FK`),
  KEY `transaction_verifica_president_id_FK_3c6de749_fk_OFFICER_U` (`president_id_FK`),
  KEY `transaction_verifica_returned_by_auditor__690b24a6_fk_OFFICER_U` (`returned_by_auditor_id_FK`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

/*Data for the table `transaction_verification` */

insert  into `transaction_verification`(`verification_id`,`table_name`,`record_id`,`verification_status`,`verified_at`,`approved_at`,`auditor_id_FK`,`president_id_FK`,`auditor_remarks`,`evidence_file_hash`,`evidence_file_path`,`return_count`,`returned_by_auditor_id_FK`,`returned_reason`,`target_category`,`deposit_slip_reference`) values 
(1,'membership_fee',1,'Approved','2026-08-07 08:07:22.635861','2026-08-07 08:07:22.635861',48,48,'Auto-approved via registration final approval',NULL,NULL,0,NULL,NULL,NULL,NULL),
(2,'membership_fee',2,'Approved','2026-08-07 08:07:29.788831','2026-08-07 08:07:29.788831',48,48,'Auto-approved via registration final approval',NULL,NULL,0,NULL,NULL,NULL,NULL),
(3,'membership_fee',3,'Approved','2026-08-07 08:07:36.171821','2026-08-07 08:07:36.171821',48,48,'Auto-approved via registration final approval',NULL,NULL,0,NULL,NULL,NULL,NULL),
(4,'monthly_dues',1,'Approved','2026-08-07 08:22:01.074304','2026-08-07 08:26:29.653044',50,48,'Reviewed by JAYEM REOJANO',NULL,NULL,0,NULL,NULL,'payment',NULL),
(5,'monthly_dues',2,'Approved','2026-08-07 08:22:01.074304','2026-08-07 08:26:13.472460',50,48,'Reviewed by JAYEM REOJANO',NULL,NULL,0,NULL,NULL,'payment',NULL),
(6,'monthly_dues',3,'Approved','2026-08-07 08:32:13.147895','2026-08-07 08:33:57.108151',50,48,'Reviewed by JAYEM REOJANO',NULL,NULL,0,NULL,NULL,NULL,NULL),
(7,'monthly_dues',4,'Approved','2026-08-07 08:32:13.147895','2026-08-07 08:34:10.276219',50,48,'Reviewed by JAYEM REOJANO',NULL,NULL,0,NULL,NULL,NULL,NULL),
(8,'monthly_dues',5,'Approved','2026-08-07 08:32:13.147895','2026-08-07 08:34:16.271121',50,48,'Reviewed by JAYEM REOJANO',NULL,NULL,0,NULL,NULL,NULL,NULL),
(9,'monthly_dues',6,'Approved','2026-08-07 08:37:48.190163','2026-08-07 08:38:20.981655',50,48,'Reviewed by JAYEM REOJANO',NULL,NULL,0,NULL,NULL,NULL,NULL),
(10,'medical_aid',1,'Approved','2026-08-07 08:41:16.964124','2026-08-07 08:54:05.115791',50,48,'Reviewed by JAYEM REOJANO',NULL,NULL,0,NULL,NULL,NULL,NULL);

/* Procedure structure for procedure `reset_app_data` */

/*!50003 DROP PROCEDURE IF EXISTS  `reset_app_data` */;

DELIMITER $$

/*!50003 CREATE DEFINER=`root`@`localhost` PROCEDURE `reset_app_data`()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE tbl_name VARCHAR(64);

    DECLARE cur CURSOR FOR
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME NOT IN (
              'officer_user',
              'django_migrations',
              'django_content_type',
              'auth_permission',
              'auth_group',
              'auth_group_permissions',
              'django_admin_log',
              'django_session'
          );

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN cur;

    read_loop: LOOP
        FETCH cur INTO tbl_name;
        IF done THEN
            LEAVE read_loop;
        END IF;

        SET @sql = CONCAT('TRUNCATE TABLE `', tbl_name, '`');
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END LOOP;

    CLOSE cur;

    DELETE FROM officer_user
    WHERE username NOT IN ('system_backfill', 'adminvon');
END */$$
DELIMITER ;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
