<!-- markdownlint-disable -->

<a href="../src/database.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `database.py`
Provide the DatabaseObserver class to handle database relation and state. 

**Global Variables**
---------------
- **DATABASE_NAME**


---

## <kbd>class</kbd> `DatabaseHandler`
The Database relation observer. 

<a href="../src/database.py#L18"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase, relation_name)
```

Initialize the observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm to attach the observer to. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/database.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_relation_data`

```python
get_relation_data() → Dict[str, str]
```

Get database data from relation. 



**Returns:**
 
 - <b>`Dict`</b>:  Information needed for setting environment variables. Returns default if the relation data is not correctly initialized. 

---

<a href="../src/database.py#L79"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `is_relation_ready`

```python
is_relation_ready() → bool
```

Check if the relation is ready. 



**Returns:**
 
 - <b>`bool`</b>:  returns True if the relation is ready. 


