"""
The Bottle module is for anything related to extracting repository data from various sources, and, 
specifically, providing RESTful CRUD (create, read, update, delete) operations relating to this repository data, 
providing the interface with our persistance layer.

These sources could include:
    GitHub's multiple APIs (default repo information, contributor networks, SBOMs, etc.)
    Google's BigQuery data about a repository
    PyPi data about a repository
    Data provided by cloning the repository and mining with PyDriller
    Custom data provided by a user
and so on.

Note: Each of these data bottles are based on a proper subset of repositories stored in a harvest. A bottle can contain
data for one repository, or it can contain the data for many repositories. Each bottle will contain the same fields for 
all repositories. It will also contain meta information about when the bottling happened.
"""