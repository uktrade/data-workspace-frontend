## Run the following statements to set up the Editor role:

`\c superset`

`INSERT INTO ab_role VALUES (7, 'Editor');`

`CREATE SEQUENCE ab_role_seq;`

`SELECT setval('ab_role_seq', 400);`

`ALTER TABLE ab_permission_view_role ALTER COLUMN id SET DEFAULT nextval('ab_role_seq');`

`insert into ab_permission_view_role (permission_view_id, role_id) values (1, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (2, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (3, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (4, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (5, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (6, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (7, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (8, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (9, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (10, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (11, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (13, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (15, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (16, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (17, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (19, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (22, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (23, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (24, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (25, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (30, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (31, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (39, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (40, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (41, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (42, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (43, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (44, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (45, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (46, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (47, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (48, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (49, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (50, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (51, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (52, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (53, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (54, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (55, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (57, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (58, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (59, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (60, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (61, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (62, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (64, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (65, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (66, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (67, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (68, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (70, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (71, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (72, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (73, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (74, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (75, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (76, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (77, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (78, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (79, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (80, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (81, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (82, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (83, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (84, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (85, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (86, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (87, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (88, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (89, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (90, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (91, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (92, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (93, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (94, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (95, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (96, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (97, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (98, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (99, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (100, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (101, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (102, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (103, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (104, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (105, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (106, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (107, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (108, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (109, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (110, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (111, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (112, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (113, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (114, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (116, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (117, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (118, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (120, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (122, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (123, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (124, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (127, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (128, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (129, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (130, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (131, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (132, 7);`

`insert into ab_permission_view_role (permission_view_id, role_id) values (135, 7);`
