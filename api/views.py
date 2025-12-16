# api/views.py
from rest_framework import status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Document
from .serializers import DocumentSerializer
from .dbManager.VectorDBManager import VectorDBManager
import uuid


# 简单注册视图
class SimpleRegisterView(APIView):
    permission_classes = []

    # api/views.py - SimpleRegisterView 的 create 方法修改

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        username = validated_data.get('username')

        # 生成用户名（如果未提供）
        if not username:
            # 清理邮箱前缀中的特殊字符
            email_prefix = email.split('@')[0]
            # 只保留字母数字
            import re
            clean_prefix = re.sub(r'[^a-zA-Z0-9]', '', email_prefix)
            if not clean_prefix:  # 如果清理后为空
                clean_prefix = "user"
            username = f"{clean_prefix}_{uuid.uuid4().hex[:6]}"

        # 确保用户名唯一
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # 创建用户
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        return user

    def to_representation(self, instance):
        # 返回用户数据时包含用户名
        return {
            'id': instance.id,
            'username': instance.username,
            'email': instance.email
        }

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {"error": "Email and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查邮箱是否已存在
        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "Email already registered"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 生成唯一用户名（使用邮箱前缀 + 随机字符串）
        email_prefix = email.split('@')[0]
        username = f"{email_prefix}_{uuid.uuid4().hex[:6]}"

        # 确保用户名唯一
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        # 创建用户
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # 生成JWT token
            refresh = RefreshToken.for_user(user)

            return Response({
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "message": "User created successfully"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Failed to create user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# 简单登录视图
class SimpleLoginView(APIView):
    permission_classes = []

    def post(self, request):
        identifier = request.data.get('username') or request.data.get('email')
        password = request.data.get('password')

        if not identifier or not password:
            return Response(
                {"error": "Username/email and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 首先尝试用用户名认证
        user = authenticate(username=identifier, password=password)

        # 如果失败，尝试查找邮箱对应的用户
        if user is None:
            try:
                # 通过邮箱查找用户
                user_by_email = User.objects.get(email=identifier)
                # 用找到的用户名尝试认证
                user = authenticate(username=user_by_email.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is not None:
            # 生成JWT token
            refresh = RefreshToken.for_user(user)

            return Response({
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "message": "Login successful"
            })
        else:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )


# 获取当前用户信息
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email
        })


class UserQueryView(APIView):
    permission_classes = []

    def post(self, request):
        query_type = request.data.get('type')
        region = request.data.get('region')
        industry = request.data.get('industry')
        context = request.data.get('context')

        if not context:
            return Response(
                {"error": "context is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            query_result = self.handle_user_query(
                query_type=query_type,
                region=region,
                industry=industry,
                context=context
            )
            return Response(query_result, status=status.HTTP_200_OK)
        except ValueError as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as error:
            return Response(
                {
                    "error": "Failed to process user query",
                    "details": str(error)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def handle_user_query(self, query_type, region, industry, context):
        if not context:
            raise ValueError("context is required")

        user_filters = {}
        if query_type:
            user_filters["type"] = query_type
        if region:
            user_filters["region"] = region
        if industry:
            user_filters["industry"] = industry

        query_fragments = [context]
        for fragment in (query_type, region, industry):
            if fragment:
                query_fragments.append(fragment)
        combined_query_text = " ".join(query_fragments)

        vector_database_manager = VectorDBManager()
        search_result = vector_database_manager.dual_matching(
            user_query=combined_query_text,
            user_filters=user_filters
        )

        return {
            "query": {
                "type": query_type,
                "region": region,
                "industry": industry,
                "context": context,
                "combined": combined_query_text
            },
            "filters": user_filters,
            "best_contract": search_result.get("best_contract"),
            "alternative_contracts": search_result.get("alternative_contracts"),
            "relevant_laws": search_result.get("relevant_laws"),
            "relevant_case": search_result.get("relevant_case")
        }


# 原有的DocumentViewSet保持不变
class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(author=self.request.user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)