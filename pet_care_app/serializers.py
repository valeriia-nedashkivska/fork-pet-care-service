import uuid
import boto3
from botocore.config import Config
from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import *


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ['full_name', 'email', 'photo_url', 'password']


class SignUpSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(write_only=True)
    photo = serializers.ImageField(required=False)

    def create(self, validated_data):
        photo = validated_data.pop("photo", None)
        user = User(
            full_name=validated_data["full_name"],
            email=validated_data["email"]
        )
        user.set_password(validated_data["password"])
        user.save()

        if photo:
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
                config=Config(s3={'use_accelerate_endpoint': True})
            )
            key = f"user_profile/image_{user.id}_{uuid.uuid4().hex}.jpg"
            s3.upload_fileobj(
                photo.file,
                settings.AWS_STORAGE_BUCKET_NAME,
                key
            )
            user.photo_url = (
                f"https://{settings.AWS_STORAGE_BUCKET_NAME}"
                f".s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{key}"
            )
            user.save()
        return user


class PetSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    photo = serializers.ImageField(required=False, write_only=True)

    class Meta:
        model = Pet
        fields = ['id', 'pet_name', 'breed', 'sex', 'birthday', 'photo_url', 'photo']
        read_only_fields = ['id', 'photo_url']

    def _upload_to_s3(self, file_obj, prefix: str):
        client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        key = f"{prefix}/image_{uuid.uuid4().hex}"
        client.upload_fileobj(file_obj, settings.AWS_STORAGE_BUCKET_NAME, key)
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3-accelerate.amazonaws.com/{key}"

    def create(self, validated_data):
        photo = validated_data.pop('photo', None)
        pet = Pet.objects.create(**validated_data)
        if photo:
            pet.photo_url = self._upload_to_s3(photo.file, f"pet_photos/pet_{pet.id}")
            pet.save()
        return pet

    def update(self, instance, validated_data):
        photo = validated_data.pop('photo', None)
        instance = super().update(instance, validated_data)
        if photo:
            instance.photo_url = self._upload_to_s3(photo.file, f"pet_photos/pet_{instance.id}")
            instance.save()
        return instance


class CalendarEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarEvent
        fields = ['id', 'pet', 'event_type', 'event_title', 'start_date', 'start_time', 'description', 'completed']


class JournalEntrySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = JournalEntry
        fields = ['id', 'pet', 'entry_type', 'entry_title', 'created_at', 'description']
        read_only_fields = ['id', 'created_at']


class SitePartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = SitePartner
        fields = ['id', 'site_name', 'site_url', 'partner_type', 'rating', 'photo_url']


class ForumCommentSerializer(serializers.ModelSerializer):
    user_full = serializers.ReadOnlyField(source='user.full_name')

    class Meta:
        model = ForumComment
        fields = ['id', 'user_full', 'comment_text', 'created_at']


class ForumPostSerializer(serializers.ModelSerializer):
    user_full = serializers.ReadOnlyField(source='user.full_name')
    user_photo = serializers.ReadOnlyField(source='user.photo_url')
    likes_count = serializers.SerializerMethodField()
    has_liked = serializers.SerializerMethodField()
    comments = ForumCommentSerializer(many=True, read_only=True)
    post_text = serializers.CharField(allow_blank=True, required=False)
    photo = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = ForumPost
        fields = [
            'id', 'user_full', 'user_photo', 'post_text', 'post_text', 'photo_url', 'photo', 'created_at',
            'likes_count', 'has_liked', 'comments'
        ]

    def _upload_to_s3(self, file_obj, prefix: str):
        client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            config=Config(s3={'use_accelerate_endpoint': True})
        )
        key = f"{prefix}/image_{uuid.uuid4().hex}"
        client.upload_fileobj(file_obj, settings.AWS_STORAGE_BUCKET_NAME, key)
        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3-accelerate.amazonaws.com/{key}"

    def create(self, validated_data):
        photo = validated_data.pop('photo', None)
        post = super().create(validated_data)
        if photo:
            post.photo_url = self._upload_to_s3(photo.file, f"forum_posts/post_{post.id}")
            post.save()
        return post

    def get_likes_count(self, obj):
        return obj.likes.count()

    def get_has_liked(self, obj):
        user = self.context['request'].user
        return user.is_authenticated and obj.likes.filter(user=user).exists()


class PartnerWatchlistSerializer(serializers.ModelSerializer):
    partner_id = serializers.IntegerField(source='partner.id')

    class Meta:
        model = PartnerWatchlist
        fields = ('partner_id',)
