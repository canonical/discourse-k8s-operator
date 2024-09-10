<!-- markdownlint-disable -->

<a href="../src/charm.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm.py`
Charm for Discourse on kubernetes. 

**Global Variables**
---------------
- **DEFAULT_RELATION_NAME**
- **DATABASE_NAME**
- **DISCOURSE_PATH**
- **LOG_PATHS**
- **PROMETHEUS_PORT**
- **REQUIRED_S3_SETTINGS**
- **SCRIPT_PATH**
- **SERVICE_NAME**
- **CONTAINER_NAME**
- **CONTAINER_APP_USERNAME**
- **SERVICE_PORT**
- **SETUP_COMPLETED_FLAG_FILE**
- **DATABASE_RELATION_NAME**


---

## <kbd>class</kbd> `DiscourseCharm`
Charm for Discourse on kubernetes. 

<a href="../src/charm.py#L92"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(*args)
```

Initialize defaults and event handlers. 


---

#### <kbd>property</kbd> app

Application that this unit is part of. 

---

#### <kbd>property</kbd> charm_dir

Root directory of the charm as it is running. 

---

#### <kbd>property</kbd> config

A mapping containing the charm's config and current values. 

---

#### <kbd>property</kbd> meta

Metadata of this charm. 

---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 

---

#### <kbd>property</kbd> unit

Unit that this execution is responsible for. 




---

## <kbd>class</kbd> `MissingRedisRelationDataError`
Custom exception to be raised in case of malformed/missing redis relation data. 





---

## <kbd>class</kbd> `S3Info`
S3Info(enabled, region, bucket, endpoint) 





