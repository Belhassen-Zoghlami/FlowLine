from django.db import models

# Create your models here.
class Developer(models.Model):
    firebase_uid=models.CharField(max_length=128, unique=True)
    email=models.EmailField(unique=True)
    display_name=models.CharField(max_length=128)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_authenticated(self):
        return True
    @classmethod
    def from_claims(cls,claims):
        developer,_=cls.objects.get_or_create(
            firebase_uid=claims["uid"],
            defaults=
            {
                "email":claims.get["email",""],
                "display_name":claims.get["name",""],
            },
        )
        return developer
    def __str__(self):
        return self.email or self.firebase_uid
