from django.db import models
from django.conf import settings
# Create your models here.
from accounts.models import Developer
from pipeline.security import decrypt, encrypt

class FaultCategory(models.Model):
    IMPORT_ERROR = "import_error","Import error"
    DEPENDENCY= "dependency","Dependency problem"
    SYNTAX = "syntax","Syntax error"
    TEST_FAILURE = "test_failure","Test failure"
    TIMEOUT= "timeout","Timeout"
    BUILD = "build", "Build failure"
    UNKNOWN = "unknown", "Unknown"

class Repository(models.Model):
    owner = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="repositories")
    github_name= models.CharField(max_length=255)
    github_repo_id=models.BigIntegerField(null=True,blank=True)
    github_token_encrypted= models.TextField(blank=True)
    webhook_secret=models.CharField(max_length=255,blank=True)
    discord_webhook_url = models.URLField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["github_name"]
        unique_together = ("owner","github_name")

    @property
    def github_token(self):
        return decrypt(self.github_token_encrypted)

    @github_token.setter
    def github_token(self,value):
        self.github_token_encrypted=encrypt(value)

    @property
    def access_token(self):
        return self.github_token or settings.GITHUB_TOKEN

    def __str__(self):
        return self.github_name

class Problem(models.Model):
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE,related_name="problems")
    signature = models.CharField(unique=True)
    category = models.CharField(max_length=64, choices=FaultCategory.choices,default=FaultCategory.UNKNOWN)
    num_occurrences = models.PositiveIntegerField(default=1)
    blamed_commit =models.CharField(max_length=40,blank=True)
    explanation = models.TextField(blank=True)
    is_notified = models.BooleanField(default=False)
    first_occ= models.DateTimeField(auto_now_add=True)
    last_occ= models.DateTimeField(auto_now=True)

    class Meta:
        ordering=["-last_occ"]
    def __Str__(self):
        return self.signature 

class Run(models.Model):
    repository=models.ForeignKey(Repository,on_delete=models.CASCADE,related_name="runs")
    problem=models.ForeignKey(Problem,on_delete=models.SET_NULL,null=True,blank=True,related_name="runs")
    github_run_id=models.BigIntegerField()
    run_number = models.PositiveIntegerField(default=0,db_index=True)
    commit_sha=models.CharField(max_length=40,blank=True)
    branch= models.CharField(max_length=255,blank=True)
    status=models.CharField(max_length=32,blank=True)
    failed_step=models.CharField(max_length=255,blank=True)
    signature=models.TextField(blank=True)
    is_parsed=models.BooleanField(default=False)
    blamed_commit=models.CharField(max_length=40,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at"]
        unique_together= ("repository","github_run_id")
    def __str__(self):
        return f"{self.repository.github_name}#{self.github_run_id}"